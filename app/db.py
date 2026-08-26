"""SQLite database module — schema, seed data, and connection management."""

from __future__ import annotations

import sqlite3
import threading
from typing import Optional

_local = threading.local()
_db_uri: str = "file:rewardbank_mem?mode=memory&cache=shared"


def set_db_uri(uri: str) -> None:
    """Set the database URI for new connections."""
    global _db_uri
    _db_uri = uri


def get_db() -> sqlite3.Connection:
    """Get or create a thread-local database connection sharing the same in-memory DB."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(_db_uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _local.conn = conn
    return _local.conn


def close_db() -> None:
    """Close the thread-local database connection."""
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def reset_db() -> None:
    """Reset the shared in-memory database by dropping tables."""
    close_db()
    db = get_db()
    db.executescript("""
        DROP TABLE IF EXISTS usage_sessions;
        DROP TABLE IF EXISTS ledger;
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS families;
    """)
    db.commit()


def init_schema(conn: Optional[sqlite3.Connection] = None) -> None:
    """Create all tables if they don't exist."""
    db = conn or get_db()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS families (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            family_id TEXT NOT NULL REFERENCES families(id),
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('parent', 'child')),
            token TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            family_id TEXT NOT NULL REFERENCES families(id),
            child_id TEXT NOT NULL REFERENCES users(id),
            created_by TEXT NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            reward_minutes INTEGER NOT NULL CHECK(reward_minutes > 0),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'done', 'approved', 'rejected', 'undone')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id TEXT NOT NULL REFERENCES users(id),
            entry_type TEXT NOT NULL CHECK(entry_type IN ('credit', 'debit', 'reversal')),
            amount INTEGER NOT NULL CHECK(amount > 0),
            balance_after INTEGER NOT NULL,
            source_type TEXT NOT NULL CHECK(source_type IN ('task_approval', 'usage_session', 'approval_reversal')),
            source_id TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_sessions (
            id TEXT PRIMARY KEY,
            child_id TEXT NOT NULL REFERENCES users(id),
            app_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            minutes_covered INTEGER NOT NULL,
            balance_exhausted_at TEXT,
            idempotency_key TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'processed'
                CHECK(status IN ('processed', 'rejected')),
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_ledger_child ON ledger(child_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_child ON tasks(child_id);
        CREATE INDEX IF NOT EXISTS idx_usage_child ON usage_sessions(child_id);
        CREATE INDEX IF NOT EXISTS idx_usage_idempotency ON usage_sessions(idempotency_key);
    """)
    db.commit()


def seed_data(conn: Optional[sqlite3.Connection] = None) -> None:
    """Seed initial data — one family, one parent, two children."""
    db = conn or get_db()

    db.execute("INSERT OR IGNORE INTO families (id, name) VALUES ('family-1', 'The Smith Family')")
    db.execute(
        "INSERT OR IGNORE INTO users (id, family_id, name, role, token) VALUES (?, ?, ?, ?, ?)",
        ("parent-1", "family-1", "Alice", "parent", "parent-token-alice"),
    )
    db.execute(
        "INSERT OR IGNORE INTO users (id, family_id, name, role, token) VALUES (?, ?, ?, ?, ?)",
        ("child-1", "family-1", "Bob", "child", "child-token-bob"),
    )
    db.execute(
        "INSERT OR IGNORE INTO users (id, family_id, name, role, token) VALUES (?, ?, ?, ?, ?)",
        ("child-2", "family-1", "Charlie", "child", "child-token-charlie"),
    )
    db.commit()


def init_db() -> sqlite3.Connection:
    """Full database initialization: schema + seed."""
    db = get_db()
    init_schema(db)
    seed_data(db)
    return db
