"""RewardBank — End-to-End System Lifecycle Demo Script.

Executes the complete lifecycle end-to-end:
1. Setup: Parent, child, starting balance
2. Child uses apps, usage sessions reported, balance draws down
3. Balance hits zero: further usage blocked, exact cutoff timestamp & covered vs rejected
4. Parent creates task, child marks done, parent approves, minutes credited
5. Child resumes usage on newly earned balance
6. Correction (undo approval) showing negative balance / debt state for minutes already spent
7. Full ledger printout and mathematical invariant assertion
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure root directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from fastapi.testclient import TestClient

from app.db import init_db, reset_db
from app.main import create_app

BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")
PARENT_TOKEN = "parent-token-alice"
CHILD_TOKEN = "child-token-bob"

_use_test_client = False
_client = None


def get_client():
    global _use_test_client, _client
    if _client is not None:
        return _client

    reset_db()
    init_db()
    app = create_app()
    _use_test_client = True
    _client = TestClient(app)
    return _client


def api(method: str, path: str, token: str, body: dict = None) -> tuple[int, dict]:
    client = get_client()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    res = client.request(method, path, json=body, headers=headers)
    return res.status_code, res.json()


def header(title: str):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def log_step(step_name: str, balance: int, new_entries: list[dict] = None):
    print(f"\n[STEP] {step_name}")
    print(f"   [BALANCE] Current Balance: {balance} minutes")
    if new_entries:
        print("   [LEDGER] Entries Created in this step:")
        for e in new_entries:
            sign = "+" if e["entryType"] == "credit" else "-"
            print(
                f"      [{e['entryType'].upper()}] {sign}{e['amount']} min "
                f"| Balance after: {e['balanceAfter']} min | {e['description']}"
            )
    else:
        print("   [LEDGER] Entries Created: (None)")


def run_demo():
    print("====================================================================")
    print("         REWARDBANK — SYSTEM LIFECYCLE DEMO TRANSCRIPT              ")
    print("====================================================================")

    # ─────────────────────────────────────────────────────────────────
    # Step 1: Setup — Parent, Child, Starting Balance
    # ─────────────────────────────────────────────────────────────────
    header("STEP 1: Setup — Parent, Child, & Initial State")
    _, bal_data = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    initial_balance = bal_data["balance"]

    _, ledger_data = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    print(f"  - Family: The Smith Family")
    print(f"  - Parent User: Alice (ID: parent-1, Token: {PARENT_TOKEN})")
    print(f"  - Child User:  Bob   (ID: child-1, Token: {CHILD_TOKEN})")
    print(f"  - Starting Balance: {initial_balance} minutes")
    print(f"  - Initial Ledger Entries Count: {len(ledger_data['entries'])}")
    log_step("Setup Complete", initial_balance)

    # Earn an initial 30 minutes balance for Bob
    _, task1 = api("POST", "/tasks", PARENT_TOKEN, {
        "childId": "child-1",
        "title": "Finish math homework",
        "rewardMinutes": 30,
    })
    api("PATCH", f"/tasks/{task1['id']}/done", CHILD_TOKEN)
    api("PATCH", f"/tasks/{task1['id']}/approve", PARENT_TOKEN)

    _, bal_after_t1 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    _, ledger_t1 = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log_step(
        "Initial Task Approved ('Finish math homework', +30 min)",
        bal_after_t1["balance"],
        [ledger_t1["entries"][-1]],
    )

    # ─────────────────────────────────────────────────────────────────
    # Step 2 & 3: Child Uses Apps, Balance Draws Down & Hits Zero
    # ─────────────────────────────────────────────────────────────────
    header("STEPS 2 & 3: App Usage, Balance Drawdown & Zero Exhaustion Cutoff")

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=40)
    end_time = now

    print(f"  - Bob submits YouTube usage session:")
    print(f"     - App: YouTube")
    print(f"     - Start: {start_time.isoformat()}")
    print(f"     - End:   {end_time.isoformat()}")
    print(f"     - Requested Duration: 40 minutes")
    print(f"     - Available Balance:  30 minutes")

    _, usage1_res = api("POST", "/usage", CHILD_TOKEN, {
        "sessions": [
            {
                "appId": "youtube",
                "startTime": start_time.isoformat(),
                "endTime": end_time.isoformat(),
            }
        ]
    })
    u1 = usage1_res["results"][0]

    print(f"\n  [RESULT] Session Processing:")
    print(f"     - Status: {u1['status']}")
    print(f"     - Minutes Covered: {u1['minutesCovered']} / {u1['durationMinutes']} min")
    print(f"     - Exact Cutoff Timestamp (Balance Exhausted At): {u1['balanceExhaustedAt']}")

    # Attempt further usage when balance is zero
    print(f"\n  [BLOCKED] Bob attempts further usage on TikTok (10 min) while balance is 0:")
    _, usage2_res = api("POST", "/usage", CHILD_TOKEN, {
        "sessions": [
            {
                "appId": "tiktok",
                "startTime": (now + timedelta(minutes=1)).isoformat(),
                "endTime": (now + timedelta(minutes=11)).isoformat(),
            }
        ]
    })
    u2 = usage2_res["results"][0]
    print(f"     - Status: {u2['status']}")
    print(f"     - Minutes Covered: {u2['minutesCovered']} / {u2['durationMinutes']} min (BLOCKED)")

    _, bal_step3 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    _, ledger_step3 = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log_step(
        "Balance Hits Zero & Further Usage Blocked",
        bal_step3["balance"],
        [ledger_step3["entries"][-1]],
    )

    # ─────────────────────────────────────────────────────────────────
    # Step 4: Parent Creates Task, Child Marks Done, Parent Approves
    # ─────────────────────────────────────────────────────────────────
    header("STEP 4: Parent Creates Task, Child Marks Done, Parent Approves")

    _, task2 = api("POST", "/tasks", PARENT_TOKEN, {
        "childId": "child-1",
        "title": "Clean bedroom & study table",
        "rewardMinutes": 50,
    })
    print(f"  1. Parent creates task: \"{task2['title']}\" (+{task2['rewardMinutes']} min reward)")

    _, task2_done = api("PATCH", f"/tasks/{task2['id']}/done", CHILD_TOKEN)
    print(f"  2. Child marks task as DONE (status: '{task2_done['status']}')")

    _, task2_app = api("PATCH", f"/tasks/{task2['id']}/approve", PARENT_TOKEN)
    print(f"  3. Parent APPROVES task (status: '{task2_app['status']}')")

    _, bal_step4 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    _, ledger_step4 = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log_step(
        "Task Approved & Minutes Credited (+50 min)",
        bal_step4["balance"],
        [ledger_step4["entries"][-1]],
    )

    # ─────────────────────────────────────────────────────────────────
    # Step 5: Child Resumes Usage on Newly Earned Balance
    # ─────────────────────────────────────────────────────────────────
    header("STEP 5: Child Resumes Usage on Newly Earned Balance")

    usage3_start = now + timedelta(minutes=15)
    usage3_end = now + timedelta(minutes=35)

    print(f"  - Bob plays Minecraft using newly earned balance (20 min session)")
    _, usage3_res = api("POST", "/usage", CHILD_TOKEN, {
        "sessions": [
            {
                "appId": "minecraft",
                "startTime": usage3_start.isoformat(),
                "endTime": usage3_end.isoformat(),
            }
        ]
    })
    u3 = usage3_res["results"][0]
    print(f"     - App: Minecraft | Covered: {u3['minutesCovered']}/{u3['durationMinutes']} min | Status: {u3['status']}")

    _, bal_step5 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    _, ledger_step5 = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log_step(
        "Usage Resumed on Earned Balance (-20 min)",
        bal_step5["balance"],
        [ledger_step5["entries"][-1]],
    )

    # ─────────────────────────────────────────────────────────────────
    # Step 6: Correction (Undo Approval) Showing Negative Balance / Debt
    # ─────────────────────────────────────────────────────────────────
    header("STEP 6: Correction (Undo Approval) & Negative Balance Debt State")

    print(f"  - Parent realizes: \"Wait, bedroom wasn't cleaned properly!\"")
    print(f"  - Parent undoes approval for task: \"{task2['title']}\" (-50 min reversal)")

    _, undo_res = api("POST", f"/tasks/{task2['id']}/undo-approval", PARENT_TOKEN)
    reversal_entry = undo_res["reversal"]

    print(f"     - Task Status: {undo_res['task']['status']}")
    print(f"     - Reversal Amount: -{reversal_entry['amount']} min")
    print(f"     - Balance After Reversal: {reversal_entry['balanceAfter']} min")
    if undo_res.get("warning"):
        print(f"     - [WARNING] {undo_res['warning']}")

    _, bal_step6 = api("GET", "/children/child-1/balance", PARENT_TOKEN)
    _, ledger_step6 = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    log_step(
        "Task Approval Undone (Compensating Reversal Created)",
        bal_step6["balance"],
        [ledger_step6["entries"][-1]],
    )

    # ─────────────────────────────────────────────────────────────────
    # Final Transcript & Invariant Verification
    # ─────────────────────────────────────────────────────────────────
    header("FINAL AUDIT & LEDGER INVARIANT VERIFICATION")

    _, final_ledger = api("GET", "/children/child-1/ledger", PARENT_TOKEN)
    entries = final_ledger["entries"]

    print("\n  Complete Chronological Ledger Table:")
    print("  +-----+----------+--------+----------+-------------------------------------------------------------+")
    print("  |  #  |   Type   | Amount | Balance  | Description                                                 |")
    print("  +-----+----------+--------+----------+-------------------------------------------------------------+")

    computed_sum = 0
    for i, e in enumerate(entries):
        sign = "+" if e["entryType"] == "credit" else "-"
        amt_str = f"{sign}{e['amount']}"
        if e["entryType"] == "credit":
            computed_sum += e["amount"]
        else:
            computed_sum -= e["amount"]

        desc = (e["description"] or "")[:59]
        print(
            f"  | {str(i + 1).rjust(3)} | {e['entryType'].ljust(8)} | "
            f"{amt_str.rjust(6)} | {str(e['balanceAfter']).rjust(8)} | "
            f"{desc.ljust(59)} |"
        )
    print("  +-----+----------+--------+----------+-------------------------------------------------------------+")

    final_balance = final_ledger["currentBalance"]
    server_computed = final_ledger["computedBalance"]
    invariant_holds = final_ledger["invariantHolds"] and (computed_sum == final_balance)

    print("\n  Final Summary Statistics:")
    print(f"     - Total Ledger Transactions: {len(entries)}")
    print(f"     - Final Reported Balance:   {final_balance} minutes")
    print(f"     - Computed Ledger Sum:      {computed_sum} minutes")
    print(f"     - Server Computed Balance:  {server_computed} minutes")
    print(f"     - Invariant Assertion:      {'HOLDS (EXACT MATCH)' if invariant_holds else 'VIOLATED'}")

    assert invariant_holds, "Ledger invariant check failed!"

    print("\n====================================================================")
    print("         DEMO COMPLETE — ALL SYSTEM INVARIANTS VERIFIED             ")
    print("====================================================================\n")


if __name__ == "__main__":
    run_demo()
