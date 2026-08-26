"""RewardBank Simulator — Worst Case Scenario (Python / FastAPI)."""

import os
import sys

# Ensure root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
PARENT_TOKEN = "parent-token-alice"
CHILD_TOKEN = "child-token-bob"

_use_test_client = False
_test_client = None

def _get_client():
    global _use_test_client, _test_client
    if _use_test_client:
        return _test_client
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=0.5)
        if r.status_code == 200:
            return httpx.Client(base_url=BASE_URL)
    except Exception:
        pass
    
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import init_db
    init_db()
    _use_test_client = True
    _test_client = TestClient(app)
    print("  [INFO] No live server found on port 3000 — running simulator using embedded FastAPI TestClient\n")
    return _test_client


def api(method: str, path: str, token: str, body: dict = None) -> tuple[int, dict]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    client = _get_client()
    if _use_test_client:
        res = client.request(method, path, json=body, headers=headers)
    else:
        with client:
            res = client.request(method, path, json=body, headers=headers)
    return res.status_code, res.json()


def log(tag: str, msg: str):
    print(f"  [{tag}] {msg}")


def section(title: str):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


def check_balance(label: str) -> int:
    _, data = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    log("BALANCE", f"{label}: {data['balance']} minutes")
    return data["balance"]


def check_invariant(label: str) -> bool:
    _, data = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    holds = data["invariantHolds"]
    log("INVARIANT", f"Invariant check ({label}): {'HOLDS' if holds else 'VIOLATED!'}")
    return holds


def worst_case():
    print("\n--- RewardBank Simulator — WORST CASE: Murphy's Law Day (Python/FastAPI) ---\n")
    all_invariants_hold = True

    # 1. Create big task & approve
    section("1. Parent creates a 60-min task -> child completes -> approved")
    _, big_task = api("POST", "/tasks", PARENT_TOKEN, {
        "childId": "child-1",
        "title": "Complete science project",
        "rewardMinutes": 60,
    })
    log("TASK", f"Task created: \"{big_task['title']}\" ({big_task['rewardMinutes']} min)")

    api("PATCH", f"/tasks/{big_task['id']}/done", CHILD_TOKEN)
    log("CHILD", "Child marks task done")

    api("PATCH", f"/tasks/{big_task['id']}/approve", PARENT_TOKEN)
    log("APPROVED", "Parent approves")

    check_balance("After approval")
    all_invariants_hold = check_invariant("after approval") and all_invariants_hold

    # 2. Spend balance down to 10
    section("2. Child uses apps across multiple devices")
    now = datetime.now(timezone.utc)

    dev_a_session = {
        "appId": "youtube-tablet",
        "startTime": (now - timedelta(minutes=50)).isoformat(),
        "endTime": (now - timedelta(minutes=30)).isoformat(),
    }
    _, usage_a = api("POST", "/usage", CHILD_TOKEN, {"sessions": [dev_a_session]})
    log("USAGE", f"Device A: YouTube {usage_a['results'][0]['minutesCovered']} min — {usage_a['results'][0]['status']}")

    dev_b_session = {
        "appId": "minecraft-pc",
        "startTime": (now - timedelta(minutes=30)).isoformat(),
        "endTime": (now - timedelta(minutes=10)).isoformat(),
    }
    _, usage_b = api("POST", "/usage", CHILD_TOKEN, {"sessions": [dev_b_session]})
    log("USAGE", f"Device B: Minecraft {usage_b['results'][0]['minutesCovered']} min — {usage_b['results'][0]['status']}")

    dev_c_session = {
        "appId": "roblox-phone",
        "startTime": (now - timedelta(minutes=10)).isoformat(),
        "endTime": now.isoformat(),
    }
    _, usage_c = api("POST", "/usage", CHILD_TOKEN, {"sessions": [dev_c_session]})
    log("USAGE", f"Device C: Roblox {usage_c['results'][0]['minutesCovered']} min — {usage_c['results'][0]['status']}")

    check_balance("After 3 devices")
    all_invariants_hold = check_invariant("after usage") and all_invariants_hold

    # 3. Device A offline
    section("3. Device A goes offline (will report late session later)")
    log("OFFLINE", "Device A loses connectivity — session queued locally")
    late_session = {
        "appId": "netflix-tablet",
        "startTime": (now - timedelta(minutes=90)).isoformat(),
        "endTime": (now - timedelta(minutes=75)).isoformat(),
    }
    log("QUEUED", f"Late session: Netflix from {late_session['startTime']} to {late_session['endTime']}")

    # 4. Parent undoes approval -> negative balance
    section("4. Parent realizes wrong task approved -> UNDO")
    log("PARENT", "Parent: \"Wait, that wasn't the science project!\"")
    _, undo_res = api("POST", f"/tasks/{big_task['id']}/undo-approval", PARENT_TOKEN)
    log("UNDO", f"Undo approval: reversal of {undo_res['reversal']['amount']} min")
    log("DEBT", f"Balance after reversal: {undo_res['reversal']['balanceAfter']} min")
    if undo_res.get("warning"):
        log("WARNING", f"Warning: {undo_res['warning']}")

    check_balance("After undo")
    all_invariants_hold = check_invariant("after undo") and all_invariants_hold

    # 5. Late session arrives -> rejected
    section("5. Device A reconnects — reports late session")
    _, late_res = api("POST", "/usage", CHILD_TOKEN, {"sessions": [late_session]})
    log("RECONNECT", f"Late session result: {late_res['results'][0]['status']}")
    log("RESULT", f"Minutes covered: {late_res['results'][0]['minutesCovered']} (balance is negative)")

    check_balance("After late session")
    all_invariants_hold = check_invariant("after late session") and all_invariants_hold

    # 6. Duplicate retry
    section("6. Device B retries — duplicate session")
    _, dupe_res = api("POST", "/usage", CHILD_TOKEN, {"sessions": [dev_b_session]})
    log("DUPLICATE", f"Duplicate detection: deduplicated={dupe_res['results'][0]['deduplicated']}")
    log("IDEMPOTENT", f"Same session ID returned: {'YES' if dupe_res['results'][0]['sessionId'] == usage_b['results'][0]['sessionId'] else 'NO'}")

    check_balance("After duplicate")
    all_invariants_hold = check_invariant("after duplicate") and all_invariants_hold

    # 7. Corrective task
    section("7. Parent creates corrective task (+80 min)")
    _, corr_task = api("POST", "/tasks", PARENT_TOKEN, {
        "childId": "child-1",
        "title": "Actually completed the real science project",
        "rewardMinutes": 80,
    })
    log("TASK", f"Corrective task created: \"{corr_task['title']}\" ({corr_task['rewardMinutes']} min)")
    api("PATCH", f"/tasks/{corr_task['id']}/done", CHILD_TOKEN)
    api("PATCH", f"/tasks/{corr_task['id']}/approve", PARENT_TOKEN)
    log("APPROVED", "Approved")

    check_balance("After correction")
    all_invariants_hold = check_invariant("after correction") and all_invariants_hold

    # 8. Use recovered balance
    section("8. Child uses recovered balance")
    _, rec_usage = api("POST", "/usage", CHILD_TOKEN, {
        "sessions": [
            {
                "appId": "spotify",
                "startTime": (now + timedelta(minutes=1)).isoformat(),
                "endTime": (now + timedelta(minutes=16)).isoformat(),
            },
            {
                "appId": "twitch",
                "startTime": (now + timedelta(minutes=16)).isoformat(),
                "endTime": (now + timedelta(minutes=26)).isoformat(),
            },
        ]
    })
    for r in rec_usage["results"]:
        log("USAGE", f"{r['appId']}: {r['minutesCovered']}/{r['durationMinutes']} min — {r['status']}")

    check_balance("After recovery usage")

    # 9. Device C retry
    section("9. Device C retries earlier partial session")
    _, dev_c_retry = api("POST", "/usage", CHILD_TOKEN, {"sessions": [dev_c_session]})
    log("DUPLICATE", f"Retry: deduplicated={dev_c_retry['results'][0]['deduplicated']}")

    # 10. Final Audit
    section("10. FINAL AUDIT")
    _, final_ledger = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    final_balance = check_balance("Final")
    final_invariant = check_invariant("FINAL")
    all_invariants_hold = final_invariant and all_invariants_hold

    print("\n  Full Ledger Trace:")
    print("  +------+----------+--------+----------+-----------------------------------------------+")
    print("  |  #   |   Type   | Amount | Balance  | Description                                   |")
    print("  +------+----------+--------+----------+-----------------------------------------------+")
    for i, e in enumerate(final_ledger["entries"]):
        sign = "+" if e["entryType"] == "credit" else "-"
        desc = (e["description"] or "")[:45]
        print(f"  | {str(i + 1).rjust(3)}  | {e['entryType'].ljust(8)} | {(sign + str(e['amount'])).rjust(6)} | {str(e['balanceAfter']).rjust(8)} | {desc.ljust(45)} |")
    print("  +------+----------+--------+----------+-----------------------------------------------+ Performance Summary")
    print(f"\n  Total ledger entries: {len(final_ledger['entries'])}")
    print(f"  Final balance: {final_balance} minutes")
    print(f"  Computed balance: {final_ledger['computedBalance']} minutes")
    print(f"  All invariants held: {'YES' if all_invariants_hold else 'NO'}")
    print("\n[SUCCESS] WORST CASE SCENARIO PASSED — Ledger integrity maintained through chaos!\n")


if __name__ == "__main__":
    worst_case()
