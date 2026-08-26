"""Children routes — balance and ledger endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.db import get_db
from app.models import BalanceResponse, LedgerResponse, User, UserRole
from app.services.ledger_service import (
    compute_balance_from_ledger,
    get_balance,
    get_ledger_history,
)

router = APIRouter(prefix="/children", tags=["children"])


def _verify_child_access(user: User, child_id: str) -> None:
    """Verify the user has access to the given child's data."""
    if user.role == UserRole.CHILD and user.id != child_id:
        raise HTTPException(
            status_code=403, detail="You can only view your own balance"
        )

    if user.role == UserRole.PARENT:
        db = get_db()
        child = db.execute(
            "SELECT family_id FROM users WHERE id = ? AND role = 'child'",
            (child_id,),
        ).fetchone()

        if not child:
            raise HTTPException(status_code=404, detail="Child not found")
        if child["family_id"] != user.family_id:
            raise HTTPException(
                status_code=403, detail="Child does not belong to your family"
            )


@router.get("/{child_id}/balance", response_model=BalanceResponse)
def get_balance_endpoint(
    child_id: str, user: User = Depends(get_current_user)
):
    """Get the current balance for a child."""
    _verify_child_access(user, child_id)

    balance = get_balance(child_id)
    return BalanceResponse(
        child_id=child_id,
        balance=balance,
        as_of=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{child_id}/ledger", response_model=LedgerResponse)
def get_ledger_endpoint(
    child_id: str, user: User = Depends(get_current_user)
):
    """Get the full ledger history for a child. Parent only."""
    if user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=403, detail="Only parents can view the ledger"
        )

    _verify_child_access(user, child_id)

    entries = get_ledger_history(child_id)
    current_balance = get_balance(child_id)
    computed_balance = compute_balance_from_ledger(child_id)

    return LedgerResponse(
        child_id=child_id,
        entries=entries,
        current_balance=current_balance,
        computed_balance=computed_balance,
        invariant_holds=(current_balance == computed_balance),
    )
