from datetime import datetime, timedelta, timezone
from tests.conftest import CHILD_TOKEN, PARENT_TOKEN


def _create_approve_task(client, reward: int) -> str:
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": f"Task {reward}", "rewardMinutes": reward},
    )
    task_id = create.json()["id"]
    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    client.patch(
        f"/tasks/{task_id}/approve",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    return task_id


def test_undo_with_full_balance_remaining(client):
    task_id = _create_approve_task(client, 30)

    undo_res = client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert undo_res.status_code == 200
    data = undo_res.json()
    assert data["task"]["status"] == "undone"
    assert data["reversal"]["entryType"] == "reversal"
    assert data["reversal"]["amount"] == 30
    assert data["reversal"]["balanceAfter"] == 0

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 0


def test_undo_after_partial_spend(client):
    task_id = _create_approve_task(client, 30)
    now = datetime.now(timezone.utc)

    client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": (now - timedelta(minutes=10)).isoformat(),
                    "endTime": now.isoformat(),
                }
            ]
        },
    )

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 20

    client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == -10


def test_undo_after_full_spend_negative_balance(client):
    task_id = _create_approve_task(client, 30)
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

    undo_res = client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert undo_res.json()["reversal"]["balanceAfter"] == -30
    assert "negative" in undo_res.json()["warning"]


def test_negative_balance_blocks_usage(client):
    task_id = _create_approve_task(client, 30)
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
    client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )

    usage_res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "tiktok",
                    "startTime": (now + timedelta(minutes=1)).isoformat(),
                    "endTime": (now + timedelta(minutes=11)).isoformat(),
                }
            ]
        },
    )
    r = usage_res.json()["results"][0]
    assert r["status"] == "rejected"
    assert r["minutesCovered"] == 0


def test_earn_back_from_negative_resumes_usage(client):
    task_id = _create_approve_task(client, 20)
    now = datetime.now(timezone.utc)

    client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": (now - timedelta(minutes=20)).isoformat(),
                    "endTime": now.isoformat(),
                }
            ]
        },
    )
    client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == -20

    # Earn 50 more -> balance = 30
    _create_approve_task(client, 50)

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 30

    usage_res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "roblox",
                    "startTime": (now + timedelta(minutes=1)).isoformat(),
                    "endTime": (now + timedelta(minutes=11)).isoformat(),
                }
            ]
        },
    )
    r = usage_res.json()["results"][0]
    assert r["status"] == "processed"
    assert r["minutesCovered"] == 10


def test_cannot_undo_unapproved_task(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Pending task", "rewardMinutes": 20},
    )
    task_id = create.json()["id"]

    res = client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 400


def test_cannot_undo_twice(client):
    task_id = _create_approve_task(client, 30)

    first = client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/tasks/{task_id}/undo-approval",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert second.status_code == 400
