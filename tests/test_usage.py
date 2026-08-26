from datetime import datetime, timedelta, timezone
from tests.conftest import CHILD_TOKEN, PARENT_TOKEN


def _give_balance(client, amount: int) -> str:
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": f"Earn {amount}", "rewardMinutes": amount},
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


def test_full_session_covered(client):
    _give_balance(client, 60)
    now = datetime.now(timezone.utc)

    res = client.post(
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
    assert res.status_code == 200
    r = res.json()["results"][0]
    assert r["durationMinutes"] == 20
    assert r["minutesCovered"] == 20
    assert r["balanceExhaustedAt"] is None
    assert r["status"] == "processed"
    assert r["deduplicated"] is False

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 40


def test_partial_session_coverage(client):
    _give_balance(client, 10)
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(minutes=20)

    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "roblox",
                    "startTime": start_time.isoformat(),
                    "endTime": now.isoformat(),
                }
            ]
        },
    )
    assert res.status_code == 200
    r = res.json()["results"][0]
    assert r["durationMinutes"] == 20
    assert r["minutesCovered"] == 10
    assert r["status"] == "processed"

    expected_exhaustion = (start_time + timedelta(minutes=10)).isoformat()
    assert r["balanceExhaustedAt"] == expected_exhaustion

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 0


def test_zero_balance_session_rejected(client):
    now = datetime.now(timezone.utc)
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "tiktok",
                    "startTime": (now - timedelta(minutes=5)).isoformat(),
                    "endTime": now.isoformat(),
                }
            ]
        },
    )
    assert res.status_code == 200
    r = res.json()["results"][0]
    assert r["minutesCovered"] == 0
    assert r["status"] == "rejected"


def test_duplicate_session_idempotent(client):
    _give_balance(client, 60)
    now = datetime.now(timezone.utc)
    session = {
        "appId": "youtube",
        "startTime": (now - timedelta(minutes=15)).isoformat(),
        "endTime": now.isoformat(),
    }

    first = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={"sessions": [session]},
    )
    assert first.json()["results"][0]["deduplicated"] is False
    assert first.json()["results"][0]["minutesCovered"] == 15

    second = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={"sessions": [session]},
    )
    assert second.json()["results"][0]["deduplicated"] is True
    assert second.json()["results"][0]["sessionId"] == first.json()["results"][0]["sessionId"]

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 45


def test_batch_sessions_sequential(client):
    _give_balance(client, 25)
    now = datetime.now(timezone.utc)

    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": (now - timedelta(minutes=30)).isoformat(),
                    "endTime": (now - timedelta(minutes=20)).isoformat(),
                },
                {
                    "appId": "minecraft",
                    "startTime": (now - timedelta(minutes=20)).isoformat(),
                    "endTime": (now - timedelta(minutes=10)).isoformat(),
                },
                {
                    "appId": "roblox",
                    "startTime": (now - timedelta(minutes=10)).isoformat(),
                    "endTime": now.isoformat(),
                },
            ]
        },
    )
    results = res.json()["results"]
    assert results[0]["minutesCovered"] == 10
    assert results[1]["minutesCovered"] == 10
    assert results[2]["minutesCovered"] == 5
    assert results[2]["balanceExhaustedAt"] is not None

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 0


def test_late_session_processed(client):
    _give_balance(client, 30)
    now = datetime.now(timezone.utc)

    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "offline-app",
                    "startTime": (now - timedelta(minutes=75)).isoformat(),
                    "endTime": (now - timedelta(minutes=60)).isoformat(),
                }
            ]
        },
    )
    assert res.json()["results"][0]["minutesCovered"] == 15

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 15


def test_invalid_dates_rejected(client):
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": "not-a-date",
                    "endTime": "also-not-a-date",
                }
            ]
        },
    )
    assert res.status_code == 400


def test_end_before_start_rejected(client):
    now = datetime.now(timezone.utc)
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": now.isoformat(),
                    "endTime": (now - timedelta(minutes=1)).isoformat(),
                }
            ]
        },
    )
    assert res.status_code == 400
