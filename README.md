# RewardBank (Python / FastAPI)

A ledger-based "screen time is earned" system built with Python, FastAPI, and SQLite. Parents create tasks; when approved, children earn screen-time minutes. Usage sessions spend minutes from the balance. Every minute earned or spent is recorded in an append-only ledger — the balance is always provable.

## Quick Start

```bash
# Create virtualenv & install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the server (FastAPI / Uvicorn on http://localhost:3000)
python3 app/main.py

# Auto-generated Swagger documentation:
# Open http://localhost:3000/docs in your browser

# Run unit & integration tests (40 tests)
PYTHONPATH=. pytest

# Run Part 5 End-to-End Demo (single command complete lifecycle transcript)
PYTHONPATH=. python3 demo.py

# Run simulators
PYTHONPATH=. python3 simulator/normal_day.py
PYTHONPATH=. python3 simulator/worst_case.py
```

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   FastAPI    │────▸│   Services   │────▸│   SQLite3    │
│   Routers    │     │  (business   │     │  (in-memory  │
│              │     │   logic)     │     │   shared)    │
│  /tasks      │     │ task_service │     │  families    │
│  /usage      │     │ ledger_svc   │     │  users       │
│  /children   │     │ usage_service│     │  tasks       │
└──────────────┘     └──────────────┘     │  ledger ◀──┐ │
       │                                  │  sessions  │ │
       ▼                                  └────────────┘ │
┌──────────────┐                           Append-only ──┘
│  HTTPBearer  │
│ Auth Dep     │
└──────────────┘
```

**Stack**: Python 3.10+ + FastAPI + Pydantic v2 + SQLite3 (built-in) + Pytest + Uvicorn

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/tasks` | Parent | Create a task for a child |
| `PATCH` | `/tasks/{id}/done` | Child | Mark own task as done |
| `PATCH` | `/tasks/{id}/approve` | Parent | Approve → credit balance |
| `PATCH` | `/tasks/{id}/reject` | Parent | Reject → no credit |
| `POST` | `/tasks/{id}/undo-approval` | Parent | Reverse approval (compensating transaction) |
| `POST` | `/usage` | Child | Report usage sessions (batch) |
| `GET` | `/children/{id}/balance` | Parent/Child | Get current balance |
| `GET` | `/children/{id}/ledger` | Parent | Full audit trail |

Interactive API documentation available at `http://localhost:3000/docs` (Swagger UI).

## Authentication

Simple token-based auth via `Authorization: Bearer <token>` header.

**Seeded users:**
| User | Role | Token |
|------|------|-------|
| Alice | Parent | `parent-token-alice` |
| Bob | Child | `child-token-bob` |
| Charlie | Child | `child-token-charlie` |

## Key Design Decisions

### 1. Append-Only Ledger
Every balance change is a ledger entry. The balance is computed from `SUM(signed amounts)` and is verifiable at any time. No mutations or deletions ever occur on the ledger table.

### 2. Corrections via Compensating Transactions
When a parent undoes an approval, the system appends a `reversal` entry (not a delete). If the child already spent minutes, the balance goes **negative** — like a real bank chargeback. The child must earn back the debt before further usage is allowed.

### 3. Idempotent Usage Sessions
Each session is identified by a SHA-256 hash of `(childId, appId, startTime, endTime)`. Duplicate submissions return the original result without double-debiting.

### 4. Partial Session Coverage
When balance runs out mid-session, the system reports exactly how many minutes were covered and the precise timestamp when the balance hit zero.

## Tests

```
✓ 40 tests passing across 5 suites

  test_invariant.py    — Ledger invariant proof (2 tests)
  test_tasks.py        — Task lifecycle & status transitions (10 tests)
  test_usage.py        — Usage, partial sessions, idempotency, batch (8 tests)
  test_corrections.py  — Undo approval scenarios & negative balance (7 tests)
  test_auth.py         — Auth & role-based security checks (13 tests)
```

## Simulator

### Normal Day (`PYTHONPATH=. python3 simulator/normal_day.py`)
Happy path: create tasks → mark done → approve/reject → use apps → check balance.

### Worst Case (`PYTHONPATH=. python3 simulator/worst_case.py`)
Murphy's Law scenario:
1. Wrong task approved, child spends most of the balance
2. Parent undoes approval → balance goes negative
3. Offline device reports late session → rejected
4. Device retries duplicate session → idempotent
5. Corrective task restores balance
6. Full ledger audit with invariant verification

## Project Structure

```
rewardbank/
├── app/
│   ├── main.py               # FastAPI app entry point & lifespan
│   ├── db.py                 # SQLite schema & thread-safe shared connection
│   ├── models.py             # Pydantic request/response models
│   ├── auth.py               # HTTPBearer auth dependencies
│   ├── routes/
│   │   ├── tasks.py          # Task CRUD endpoints
│   │   ├── usage.py          # Usage session endpoint
│   │   └── children.py       # Balance & ledger endpoints
│   └── services/
│       ├── ledger_service.py # Append-only ledger operations
│       ├── task_service.py   # Task lifecycle logic
│       └── usage_service.py  # Usage processing & idempotency
├── tests/                    # Pytest test suites (40 tests)
├── simulator/                # Python simulator scripts
├── requirements.txt          # Python dependencies
├── README.md
└── WRITEUP.md
```

## License

MIT
