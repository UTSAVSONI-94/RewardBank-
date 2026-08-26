from tests.conftest import CHILD2_TOKEN, CHILD_TOKEN, PARENT_TOKEN


def test_create_task_pending(client):
    res = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Do homework", "rewardMinutes": 30},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "pending"
    assert data["title"] == "Do homework"
    assert data["rewardMinutes"] == 30
    assert data["childId"] == "child-1"


def test_create_task_missing_fields(client):
    res = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1"},
    )
    assert res.status_code == 422  # FastAPI validation error


def test_create_task_non_positive_reward(client):
    res = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Test", "rewardMinutes": -5},
    )
    assert res.status_code == 422  # Pydantic validation error (gt=0)


def test_mark_task_done(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Clean room", "rewardMinutes": 15},
    )
    task_id = create.json()["id"]

    res = client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "done"


def test_child_cannot_mark_other_child_task_done(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Clean room", "rewardMinutes": 15},
    )
    task_id = create.json()["id"]

    res = client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD2_TOKEN}"},
    )
    assert res.status_code == 403


def test_cannot_mark_non_pending_task_done(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Clean room", "rewardMinutes": 15},
    )
    task_id = create.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    res = client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 400


def test_approve_done_task_credits_balance(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Homework", "rewardMinutes": 30},
    )
    task_id = create.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    approve = client.patch(
        f"/tasks/{task_id}/approve",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 30


def test_cannot_approve_non_done_task(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Homework", "rewardMinutes": 30},
    )
    task_id = create.json()["id"]

    res = client.patch(
        f"/tasks/{task_id}/approve",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert res.status_code == 400


def test_reject_done_task_no_balance_change(client):
    create = client.post(
        "/tasks",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
        json={"childId": "child-1", "title": "Homework", "rewardMinutes": 30},
    )
    task_id = create.json()["id"]

    client.patch(
        f"/tasks/{task_id}/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    reject = client.patch(
        f"/tasks/{task_id}/reject",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    bal = client.get(
        "/children/child-1/balance",
        headers={"Authorization": f"Bearer {PARENT_TOKEN}"},
    )
    assert bal.json()["balance"] == 0


def test_nonexistent_task_404(client):
    res = client.patch(
        "/tasks/nonexistent-id/done",
        headers={"Authorization": f"Bearer {CHILD_TOKEN}"},
    )
    assert res.status_code == 404
