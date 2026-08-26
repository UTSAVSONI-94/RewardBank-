"""Ledger service — the core accounting engine.

Append-only entries. Balance is always derived from the ledger.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_db
from app.models import LedgerEntryResponse, LedgerEntryType, LedgerSourceType


def get_balance(child_id: str) -> int:
    """Get the current balance by reading the latest ledger entry.
    If no entries exist, balance is 0.
    """
    db = get_db()
    row = db.execute(
        "SELECT balance_after FROM ledger WHERE child_id = ? ORDER BY id DESC LIMIT 1",
        (child_id,),
    ).fetchone()
    return row["balance_after"] if row else 0


def compute_balance_from_ledger(child_id: str) -> int:
    """Compute balance from scratch by summing all ledger entries.
    Used for invariant verification.
    """
    db = get_db()
    row = db.execute(
        """
        SELECT COALESCE(
            SUM(CASE
                WHEN entry_type = 'credit' THEN amount
                WHEN entry_type = 'debit' THEN -amount
                WHEN entry_type = 'reversal' THEN -amount
                ELSE 0
            END),
            0
        ) AS computed_balance
        FROM ledger
        WHERE child_id = ?
        """,
        (child_id,),
    ).fetchone()
    return row["computed_balance"]


def append_ledger_entry(
    child_id: str,
    entry_type: LedgerEntryType,
    amount: int,
    source_type: LedgerSourceType,
    source_id: str,
    description: str | None,
) -> LedgerEntryResponse:
    """Append a ledger entry — the ONLY way to modify a child's balance.

    The balance_after is computed from the current balance + the signed amount.
    """
    if amount <= 0:
        raise ValueError("Ledger entry amount must be positive")

    db = get_db()
    current_balance = get_balance(child_id)

    if entry_type == LedgerEntryType.CREDIT:
        signed_amount = amount
    else:
        # debit or reversal
        signed_amount = -amount

    balance_after = current_balance + signed_amount
    now = datetime.now(timezone.utc).isoformat()

    cursor = db.execute(
        """INSERT INTO ledger (child_id, entry_type, amount, balance_after,
           source_type, source_id, description, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (child_id, entry_type.value, amount, balance_after,
         source_type.value, source_id, description, now),
    )
    db.commit()

    entry_id = cursor.lastrowid

    return LedgerEntryResponse(
        id=entry_id,
        child_id=child_id,
        entry_type=entry_type,
        amount=amount,
        balance_after=balance_after,
        source_type=source_type,
        source_id=source_id,
        description=description,
        created_at=now,
    )


def get_ledger_history(child_id: str) -> list[LedgerEntryResponse]:
    """Get the full ledger history for a child, ordered chronologically."""
    db = get_db()
    rows = db.execute(
        """SELECT id, child_id, entry_type, amount, balance_after,
                  source_type, source_id, description, created_at
           FROM ledger WHERE child_id = ? ORDER BY id ASC""",
        (child_id,),
    ).fetchall()

    return [
        LedgerEntryResponse(
            id=row["id"],
            child_id=row["child_id"],
            entry_type=LedgerEntryType(row["entry_type"]),
            amount=row["amount"],
            balance_after=row["balance_after"],
            source_type=LedgerSourceType(row["source_type"]),
            source_id=row["source_id"],
            description=row["description"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
