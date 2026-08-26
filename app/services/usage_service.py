"""Usage service — process device usage sessions with idempotency."""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone

from app.db import get_db
from app.models import (
    LedgerEntryType,
    LedgerSourceType,
    UsageSessionInput,
    UsageSessionResult,
    UsageSessionStatus,
)
from app.services.ledger_service import append_ledger_entry, get_balance


def _generate_idempotency_key(child_id: str, session: UsageSessionInput) -> str:
    """Generate a SHA-256 idempotency key from session properties."""
    raw = f"{child_id}|{session.app_id}|{session.start_time}|{session.end_time}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _calculate_duration_minutes(start_time: str, end_time: str) -> int:
    """Calculate the duration of a session in whole minutes (ceiling)."""
    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    if end <= start:
        raise ValueError("endTime must be after startTime")

    diff_seconds = (end - start).total_seconds()
    return math.ceil(diff_seconds / 60)


def _calculate_exhaustion_timestamp(start_time: str, minutes_covered: int) -> str:
    """Calculate the exact timestamp when the balance runs out during a session."""
    start = datetime.fromisoformat(start_time)
    from datetime import timedelta

    exhausted_at = start + timedelta(minutes=minutes_covered)
    return exhausted_at.isoformat()


def _find_existing_session(idempotency_key: str) -> dict | None:
    """Check if a session with this idempotency key already exists."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM usage_sessions WHERE idempotency_key = ?",
        (idempotency_key,),
    ).fetchone()

    if not row:
        return None

    return dict(row)


def _process_single_session(
    child_id: str, session: UsageSessionInput
) -> UsageSessionResult:
    """Process a single usage session.

    Handles:
      - Idempotency (duplicate detection)
      - Partial coverage (balance runs out mid-session)
      - Zero balance (session rejected)
      - Negative balance (session rejected)
    """
    idempotency_key = _generate_idempotency_key(child_id, session)

    # Check for duplicate
    existing = _find_existing_session(idempotency_key)
    if existing:
        return UsageSessionResult(
            session_id=existing["id"],
            app_id=existing["app_id"],
            duration_minutes=existing["duration_minutes"],
            minutes_covered=existing["minutes_covered"],
            balance_exhausted_at=existing["balance_exhausted_at"],
            status=UsageSessionStatus(existing["status"]),
            deduplicated=True,
        )

    duration_minutes = _calculate_duration_minutes(session.start_time, session.end_time)
    current_balance = get_balance(child_id)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db = get_db()

    # If balance is zero or negative, reject the session
    if current_balance <= 0:
        db.execute(
            """INSERT INTO usage_sessions (id, child_id, app_id, start_time, end_time,
               duration_minutes, minutes_covered, balance_exhausted_at,
               idempotency_key, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?, 'rejected', ?)""",
            (session_id, child_id, session.app_id, session.start_time,
             session.end_time, duration_minutes, idempotency_key, now),
        )
        db.commit()

        return UsageSessionResult(
            session_id=session_id,
            app_id=session.app_id,
            duration_minutes=duration_minutes,
            minutes_covered=0,
            balance_exhausted_at=None,
            status=UsageSessionStatus.REJECTED,
            deduplicated=False,
        )

    # Calculate coverage
    minutes_covered = min(current_balance, duration_minutes)
    is_partial = minutes_covered < duration_minutes
    balance_exhausted_at = (
        _calculate_exhaustion_timestamp(session.start_time, minutes_covered)
        if is_partial
        else None
    )

    # Record the session
    db.execute(
        """INSERT INTO usage_sessions (id, child_id, app_id, start_time, end_time,
           duration_minutes, minutes_covered, balance_exhausted_at,
           idempotency_key, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed', ?)""",
        (session_id, child_id, session.app_id, session.start_time,
         session.end_time, duration_minutes, minutes_covered,
         balance_exhausted_at, idempotency_key, now),
    )
    db.commit()

    # Debit the ledger
    if minutes_covered > 0:
        desc = f"App usage: {session.app_id} ({minutes_covered}/{duration_minutes} min covered)"
        if is_partial:
            desc += " — balance exhausted"

        append_ledger_entry(
            child_id=child_id,
            entry_type=LedgerEntryType.DEBIT,
            amount=minutes_covered,
            source_type=LedgerSourceType.USAGE_SESSION,
            source_id=session_id,
            description=desc,
        )

    return UsageSessionResult(
        session_id=session_id,
        app_id=session.app_id,
        duration_minutes=duration_minutes,
        minutes_covered=minutes_covered,
        balance_exhausted_at=balance_exhausted_at,
        status=UsageSessionStatus.PROCESSED,
        deduplicated=False,
    )


def process_usage_batch(
    child_id: str, sessions: list[UsageSessionInput]
) -> list[UsageSessionResult]:
    """Process a batch of usage sessions sequentially."""
    results: list[UsageSessionResult] = []
    for session in sessions:
        result = _process_single_session(child_id, session)
        results.append(result)
    return results
