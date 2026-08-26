"""Usage routes — batch session reporting from devices."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_child
from app.models import UsageBatchRequest, UsageBatchResponse, User
from app.services.usage_service import process_usage_batch

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("", response_model=UsageBatchResponse)
def report_usage_endpoint(
    body: UsageBatchRequest, user: User = Depends(require_child)
):
    """Device reports usage sessions (batch)."""
    if not body.sessions:
        raise HTTPException(status_code=400, detail="Missing or empty sessions array")

    # Validate each session
    for i, s in enumerate(body.sessions):
        try:
            start = datetime.fromisoformat(s.start_time)
            end = datetime.fromisoformat(s.end_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Session at index {i} has invalid date format",
            )

        if end <= start:
            raise HTTPException(
                status_code=400,
                detail=f"Session at index {i}: endTime must be after startTime",
            )

    results = process_usage_batch(user.id, body.sessions)
    return UsageBatchResponse(results=results)
