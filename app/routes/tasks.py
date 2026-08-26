"""Task routes — create, mark done, approve, reject, undo approval."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_child, require_parent
from app.models import CreateTaskRequest, TaskResponse, UndoApprovalResponse, User
from app.services.task_service import (
    approve_task,
    create_task,
    mark_task_done,
    reject_task,
    undo_approval,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", status_code=201, response_model=TaskResponse)
def create_task_endpoint(
    body: CreateTaskRequest, user: User = Depends(require_parent)
):
    """Parent creates a task for a child."""
    try:
        task = create_task(
            child_id=body.child_id,
            title=body.title,
            reward_minutes=body.reward_minutes,
            created_by=user.id,
            family_id=user.family_id,
        )
        return task
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{task_id}/done", response_model=TaskResponse)
def mark_done_endpoint(task_id: str, user: User = Depends(require_child)):
    """Child marks their task as done."""
    try:
        return mark_task_done(task_id, user.id)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/{task_id}/approve", response_model=TaskResponse)
def approve_endpoint(task_id: str, user: User = Depends(require_parent)):
    """Parent approves a completed task → credits the child's balance."""
    try:
        return approve_task(task_id, user.id)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/{task_id}/reject", response_model=TaskResponse)
def reject_endpoint(task_id: str, user: User = Depends(require_parent)):
    """Parent rejects a completed task — no balance change."""
    try:
        return reject_task(task_id, user.id)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/{task_id}/undo-approval", response_model=UndoApprovalResponse)
def undo_approval_endpoint(task_id: str, user: User = Depends(require_parent)):
    """Parent undoes an approval — compensating reversal on the ledger."""
    try:
        task, reversal = undo_approval(task_id, user.id)
        warning = None
        if reversal.balance_after < 0:
            warning = (
                f"Child's balance is now negative ({reversal.balance_after} min). "
                f"They must earn back minutes before further usage is allowed."
            )
        return UndoApprovalResponse(task=task, reversal=reversal, warning=warning)
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
