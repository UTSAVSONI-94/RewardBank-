"""RewardBank Simulator — Normal Day Scenario (Python / FastAPI)."""

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
        # Check if server is running
        r = httpx.get(f"{BASE_URL}/health", timeout=0.5)
        if r.status_code == 200:
            return httpx.Client(base_url=BASE_URL)
    except Exception:
        pass
    
    # Fallback to FastAPI TestClient
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
    data = res.json()
    if res.status_code >= 400:
        print(f"  [ERROR] {method} {path} -> {res.status_code}: {data}")
    return res.status_code, data


def log(msg: str):
    print(f"  [LOG] {msg}")


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def normal_day():
    print("\n--- RewardBank Simulator — Normal Day Scenario (Python/FastAPI) ---\n")

    # 1. Create Tasks
    section("1. Parent creates 3 tasks")
    tasks = [
        {"childId": "child-1", "title": "Finish math homework", "rewardMinutes": 30},
        {"childId": "child-1", "title": "Clean your room", "rewardMinutes": 20},
        {"childId": "child-1", "title": "Practice piano", "rewardMinutes": 15},
    ]
    task_ids = []
    for task in tasks:
        _, data = api("POST", "/tasks", PARENT_TOKEN, task)
        task_ids.append(data["id"])
        log(f"Created: \"{task['title']}\" — {task['rewardMinutes']} min reward -> ID: {data['id'][:8]}...")

    # 2. Child marks done
    section("2. Child marks all tasks as done")
    for i, t_id in enumerate(task_ids):
        api("PATCH", f"/tasks/{t_id}/done", CHILD_TOKEN)
        log(f"Marked done: \"{tasks[i]['title']}\"")

    # 3. Parent reviews
    section("3. Parent reviews tasks")
    api("PATCH", f"/tasks/{task_ids[0]}/approve", PARENT_TOKEN)
    log(f"[APPROVED] \"{tasks[0]['title']}\" (+{tasks[0]['rewardMinutes']} min)")

    api("PATCH", f"/tasks/{task_ids[1]}/approve", PARENT_TOKEN)
    log(f"[APPROVED] \"{tasks[1]['title']}\" (+{tasks[1]['rewardMinutes']} min)")

    api("PATCH", f"/tasks/{task_ids[2]}/reject", PARENT_TOKEN)
    log(f"[REJECTED] \"{tasks[2]['title']}\" (room was still messy)")

    _, bal1 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    log(f"Current balance: {bal1['balance']} minutes")

    # 4. Child uses apps
    section("4. Child uses apps")
    now = datetime.now(timezone.utc)
    sessions = [
        {
            "appId": "youtube",
            "startTime": (now - timedelta(minutes=25)).isoformat(),
            "endTime": (now - timedelta(minutes=10)).isoformat(),
        },
        {
            "appId": "minecraft",
            "startTime": (now - timedelta(minutes=10)).isoformat(),
            "endTime": (now - timedelta(minutes=5)).isoformat(),
        },
        {
            "appId": "roblox",
            "startTime": (now - timedelta(minutes=5)).isoformat(),
            "endTime": now.isoformat(),
        },
    ]

    _, usage_data = api("POST", "/usage", CHILD_TOKEN, {"sessions": sessions})
    for r in usage_data["results"]:
        log(f"{r['appId']}: {r['minutesCovered']}/{r['durationMinutes']} min covered — {r['status']}")

    # 5. Final state
    section("5. Final state")
    _, bal2 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    log(f"Final balance: {bal2['balance']} minutes")

    _, ledger = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log(f"Ledger entries: {len(ledger['entries'])}")
    log(f"Invariant holds: {'YES' if ledger['invariantHolds'] else 'NO'}")

    print("\n  Ledger:")
    for entry in ledger["entries"]:
        sign = "+" if entry["entryType"] == "credit" else "-"
        print(f"    {sign}{entry['amount']} min | balance: {entry['balanceAfter']} | {entry['description']}")

    print("\n[SUCCESS] Normal day scenario complete.\n")


if __name__ == "__main__":
    normal_day()
