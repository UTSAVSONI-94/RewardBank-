from tests.conftest import CHILD2_TOKEN, CHILD_TOKEN, PARENT_TOKEN


def test_missing_auth_header_401(client):
    res = client.get("/children/child-1/balance")
    assert res.status_code == 403 or res.status_code == 401  # FastAPI HTTPBearer returns 403 or 401 if missing header


def test_invalid_token_401(client):
    res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": "Bearer invalid-token-xyz"},
    )
    assert res.status_code == 401


def test_child_cannot_create_tasks(client):
    res = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
        json={"childId": "child-1", "title": "Test", "rewardMinutes": 10},
    )
    assert res.status_code == 403


def test_child_cannot_approve_tasks(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Test", "rewardMinutes": 10},
    )
    task_id = create.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )

    res = client.patch(
        f"/tasks/{task_id}/approve",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 403


def test_child_cannot_reject_tasks(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Test", "rewardMinutes": 10},
    )
    task_id = create.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )

    res = client.patch(
        f"/tasks/{task_id}/reject",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 403


def test_child_cannot_undo_approvals(client):
    res = client.post(
        "/tasks/some-id/undo-approval",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 403


def test_parent_cannot_mark_tasks_done(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Test", "rewardMinutes": 10},
    )
    task_id = create.json()["id"]

    res = client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 403


def test_parent_cannot_report_usage(client):
    res = client.post(
        "/usage",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={
            "sessions": [
                {
                    "appId": "youtube",
                    "startTime": "2026-08-26T10:00:00Z",
                    "endTime": "2026-08-26T10:10:00Z",
                }
            ]
        },
    )
    assert res.status_code == 403


def test_child_can_view_own_balance(client):
    res = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 200


def test_child_cannot_view_other_child_balance(client):
    res = client.get(
        "/children/child-2/balance",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 403


def test_child_cannot_view_ledger(client):
    res = client.get(
        "/children/child-1/ledger",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 403


def test_parent_can_view_ledger(client):
    res = client.get(
        "/children/child-1/ledger",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 200


def test_health_check_no_auth(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "RewardBank"
