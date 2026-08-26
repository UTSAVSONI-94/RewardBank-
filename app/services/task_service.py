"""Task service — create, mark done, approve, reject, undo approval."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models import (
    LedgerEntryResponse,
    LedgerEntryType,
    LedgerSourceType,
    TaskResponse,
    TaskStatus,
)
from app.services.ledger_service import append_ledger_entry, get_balance


def _row_to_task(row) -> TaskResponse:
    """Convert a database row to a TaskResponse."""
    return TaskResponse(
        id=row["id"],
        family_id=row["family_id"],
        child_id=row["child_id"],
        created_by=row["created_by"],
        title=row["title"],
        reward_minutes=row["reward_minutes"],
        status=TaskStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_task(task_id: str) -> TaskResponse | None:
    """Get a task by ID."""
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def create_task(
    child_id: str,
    title: str,
    reward_minutes: int,
    created_by: str,
    family_id: str,
) -> TaskResponse:
    """Create a new task assigned to a child."""
    db = get_db()

    # Verify the child exists and belongs to the same family
    child = db.execute(
        "SELECT id, family_id, role FROM users WHERE id = ?", (child_id,)
    ).fetchone()

    if not child:
        raise ValueError("Child not found")
    if child["family_id"] != family_id:
        raise ValueError("Child does not belong to your family")
    if child["role"] != "child":
        raise ValueError("Target user is not a child")

    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        """INSERT INTO tasks (id, family_id, child_id, created_by, title,
           reward_minutes, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (task_id, family_id, child_id, created_by, title, reward_minutes, now, now),
    )
    db.commit()

    return TaskResponse(
        id=task_id,
        family_id=family_id,
        child_id=child_id,
        created_by=created_by,
        title=title,
        reward_minutes=reward_minutes,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
    )


def _update_task_status(
    task_id: str,
    new_status: TaskStatus,
    allowed_from: list[TaskStatus],
) -> TaskResponse:
    """Update a task's status with validation of allowed transitions."""
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    if task.status not in allowed_from:
        raise ValueError(
            f"Cannot transition from '{task.status.value}' to '{new_status.value}'. "
            f"Allowed from: {', '.join(s.value for s in allowed_from)}"
        )

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
        (new_status.value, now, task_id),
    )
    db.commit()

    return TaskResponse(
        id=task.id,
        family_id=task.family_id,
        child_id=task.child_id,
        created_by=task.created_by,
        title=task.title,
        reward_minutes=task.reward_minutes,
        status=new_status,
        created_at=task.created_at,
        updated_at=now,
    )


def mark_task_done(task_id: str, child_id: str) -> TaskResponse:
    """Child marks their task as done."""
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")
    if task.child_id != child_id:
        raise PermissionError("This task is not assigned to you")

    return _update_task_status(task_id, TaskStatus.DONE, [TaskStatus.PENDING])


def _verify_parent_family(parent_id: str, task_family_id: str) -> None:
    """Verify a parent belongs to the same family as the task."""
    db = get_db()
    parent = db.execute(
        "SELECT family_id FROM users WHERE id = ?", (parent_id,)
    ).fetchone()

    if not parent:
        raise ValueError("Parent not found")
    if parent["family_id"] != task_family_id:
        raise PermissionError("Task does not belong to your family")


def approve_task(task_id: str, parent_id: str) -> TaskResponse:
    """Parent approves a completed task → credit the child's balance."""
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    _verify_parent_family(parent_id, task.family_id)

    updated_task = _update_task_status(task_id, TaskStatus.APPROVED, [TaskStatus.DONE])

    # Credit the child's balance via the ledger
    append_ledger_entry(
        child_id=task.child_id,
        entry_type=LedgerEntryType.CREDIT,
        amount=task.reward_minutes,
        source_type=LedgerSourceType.TASK_APPROVAL,
        source_id=task_id,
        description=f'Approved task: "{task.title}" (+{task.reward_minutes} min)',
    )

    return updated_task


def reject_task(task_id: str, parent_id: str) -> TaskResponse:
    """Parent rejects a completed task — no balance change."""
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    _verify_parent_family(parent_id, task.family_id)

    return _update_task_status(task_id, TaskStatus.REJECTED, [TaskStatus.DONE])


def undo_approval(
    task_id: str, parent_id: str
) -> tuple[TaskResponse, LedgerEntryResponse]:
    """Parent undoes an approval — compensating reversal on the ledger.

    The child may have already spent some or all of the minutes.
    Balance can go negative (creating a "debt").
    """
    task = get_task(task_id)
    if not task:
        raise ValueError("Task not found")

    _verify_parent_family(parent_id, task.family_id)

    updated_task = _update_task_status(
        task_id, TaskStatus.UNDONE, [TaskStatus.APPROVED]
    )

    # Append a reversal entry — this may push balance negative
    ledger_entry = append_ledger_entry(
        child_id=task.child_id,
        entry_type=LedgerEntryType.REVERSAL,
        amount=task.reward_minutes,
        source_type=LedgerSourceType.APPROVAL_REVERSAL,
        source_id=task_id,
        description=(
            f'Reversed approval of task: "{task.title}" (-{task.reward_minutes} min). '
            f"Balance may be negative if minutes were already spent."
        ),
    )

    return updated_task, ledger_entry
