from datetime import datetime, timedelta, timezone
from tests.conftest import CHILD_TOKEN, PARENT_TOKEN


def test_ledger_invariant_complex_sequence(client):
    """Invariant holds: SUM(signed ledger amounts) === current balance across a complex sequence."""
    task_ids = []
    rewards = [30, 20, 15, 45, 10]

    # Step 1: Create 5 tasks
    for reward in rewards:
        res = client.post(
            "/tasks",
            headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
            json={"childId": "child-1", "title": f"Task {reward}", "rewardMinutes": reward},
        )
        assert res.status_code == 201
        task_ids.append(res.json()["id"])

    # Step 2: Child marks all tasks as done
    for task_id in task_ids:
        res = client.patch(
            f"/tasks/{task_id}/done",
            headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        )
        assert res.status_code == 200

    # Step 3: Approve 3 tasks, reject 1, leave 1 pending ('done')
    for i in range(3):
        res = client.patch(
            f"/tasks/{task_ids[i]}/approve",
            headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        )
        assert res.status_code == 200

    res = client.patch(
        f"/tasks/{task_ids[3]}/reject",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 200

    # Verify balance = 30 + 20 + 15 = 65
    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == 65

    # Step 4: Report usage sessions (20 + 10 = 30 minutes spent)
    now = datetime.now(timezone.utc)
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": (now - timedelta(minutes=30)).isoformat(),
                    "endTime": (now - timedelta(minutes=10)).isoformat(),
                },
                {
                    "appId": "minecraft",
                    "startTime": (now - timedelta(minutes=10)).isoformat(),
                    "endTime": now.isoformat(),
                },
            ]
        },
    )
    assert res.status_code == 200

    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == 35

    # Step 5: Undo approval of task 0 (reward: 30) -> balance 35 - 30 = 5
    res = client.post(
        f"/tasks/{task_ids[0]}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 200

    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == 5

    # Step 6: Report more usage (8 minutes — partially covered)
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "roblox",
                    "startTime": (now + timedelta(minutes=1)).isoformat(),
                    "endTime": (now + timedelta(minutes=9)).isoformat(),
                }
            ]
        },
    )
    assert res.status_code == 200
    result = res.json()["results"][0]
    assert result["minutesCovered"] == 5
    assert result["balanceExhaustedAt"] is not None
    assert result["status"] == "processed"

    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == 0

    # Step 7: Ledger Invariant Check
    ledger_res = client.get(
        "/children/child-1/ledger",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    data = ledger_res.json()
    entries = data["entries"]
    assert len(entries) > 0

    computed_balance = 0
    for entry in entries:
        if entry["entryType"] == "credit":
            computed_balance += entry["amount"]
        else:
            computed_balance -= entry["amount"]

    last_entry = entries[-1]
    assert computed_balance == bal_res.json()["balance"]
    assert computed_balance == last_entry["balanceAfter"]
    assert data["invariantHolds"] is True
    assert data["currentBalance"] == data["computedBalance"]


def test_ledger_invariant_negative_balance(client):
    """Invariant holds even with negative balance from undo after full spend."""
    create_res = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Homework", "rewardMinutes": 30},
    )
    task_id = create_res.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    client.patch(
        f"/tasks/{task_id}/approve",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )

    now = datetime.now(timezone.utc)
    client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "netflix",
                    "startTime": (now - timedelta(minutes=30)).isoformat(),
                    "endTime": now.isoformat(),
                }
            ]
        },
    )

    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == 0

    # Undo approval -> balance = -30
    client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )

    bal_res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal_res.json()["balance"] == -30

    ledger_res = client.get(
        "/children/child-1/ledger",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    data = ledger_res.json()

    computed_balance = 0
    for entry in data["entries"]:
        if entry["entryType"] == "credit":
            computed_balance += entry["amount"]
        else:
            computed_balance -= entry["amount"]

    assert computed_balance == -30
    assert computed_balance == bal_res.json()["balance"]
    assert data["invariantHolds"] is True
