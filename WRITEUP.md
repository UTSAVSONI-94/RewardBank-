# WRITEUP.md — RewardBank Design Document

## Overview

RewardBank is a ledger-based screen-time banking system built in Python using FastAPI, Pydantic, and SQLite. The core premise: treat screen-time minutes like money. Every minute earned or spent must be accounted for in an append-only ledger, and the balance must always be provable from that ledger.

---

## Design Philosophy

### Why a Ledger?

Real financial systems don't do `balance = balance + x`. They maintain a ledger — an append-only sequence of transactions — and the balance is always a derived value. This gives you:

1. **Auditability**: You can trace every minute to its source (which task earned it, which app spent it).
2. **Verifiability**: The balance is provable at any time by replaying the ledger.
3. **Immutability**: Once a transaction is recorded, it cannot be altered — only compensated.

RewardBank follows this pattern exactly. The `ledger` table is the source of truth. The `balance_after` field on each entry is a convenience snapshot, but the system can always recompute the balance from scratch to verify integrity.

---

## The Hardest Problem: Corrections

### The Scenario

A parent approves Task A (reward: 60 minutes). The child immediately spends 45 of those minutes. Then the parent realizes they approved the wrong task — it wasn't actually completed.

**Options considered:**

1. **Delete the original credit entry** — Violates append-only. Destroys audit trail. What happened to those 45 spent minutes?

2. **Edit the credit amount to 0** — Same problem. The ledger would show 45 minutes spent but only 0 earned, which doesn't explain the history.

3. **Prevent undo if minutes were spent** — Overly restrictive. Parents need the ability to correct mistakes.

4. **Compensating transaction (chosen)** — Append a `reversal` entry that debits the full reward amount. If the child already spent minutes, the balance goes negative.

### Why Negative Balance?

A negative balance is the *honest* state. The child used minutes they shouldn't have had. Like a bank chargeback:

- The original credit stays in the ledger (it happened)
- The debit entries stay in the ledger (they happened)
- The reversal is a new entry explaining the correction
- The negative balance is a "debt" — the child must earn more minutes before further usage is allowed

This mirrors how real financial systems handle chargebacks and reversals. No data is lost, and the full story is always readable from the ledger.

---

## Late Sessions

### The Problem

Devices go offline. When they reconnect, they report usage sessions from the past (e.g., a session from an hour ago).

### My Approach: Process Against Current Balance

Late sessions are processed against the **current** balance at the time they arrive at the server, not the balance at the time the session actually occurred.

**Why not retroactive rebalancing?**

Retroactive processing would require:
1. Finding the balance at the session's original timestamp
2. Inserting a ledger entry in the correct chronological position
3. Recomputing all subsequent `balance_after` values
4. Potentially reclassifying later sessions (some might now be partially covered or rejected)

This is a significantly more complex system that introduces its own correctness challenges (e.g., what if a reversal happened between the session time and now?). For a screen-time system (not an exchange or bank), the pragmatic approach — process on arrival — is sufficient and far simpler to reason about.

**Trade-off**: A child could theoretically benefit from a race condition where they go offline, use an app, and meanwhile spend down their balance. When the offline session arrives, there's no balance left. However, this is acceptable because:
- The session was still recorded as `rejected`
- The parent can see the attempt in the ledger
- The app should have been blocked locally when balance was known to be 0

---

## Idempotency

### The Problem

Networks are unreliable. A device reports a usage session, the server processes it, but the response is lost (timeout, connection reset). The device retries, sending the same session again.

### Solution: SHA-256 Idempotency Key

Each session is fingerprinted using `SHA-256(childId + appId + startTime + endTime)`. Before processing, the system checks for an existing session with that key:

- **Found**: Return the original result (same session ID, same coverage data). No new ledger entry.
- **Not found**: Process normally.

This guarantees that duplicate submissions are safe and transparent. The response includes a `deduplicated: True` flag so the client knows.

---

## Partial Session Coverage

### The Problem

A child has 10 minutes of balance remaining but starts a 25-minute session. The system must answer:
1. How many minutes were covered?
2. At what exact timestamp did the balance run out?

### Solution

```
minutes_covered = min(current_balance, session_duration)
balance_exhausted_at = session_start + timedelta(minutes=minutes_covered)
```

For the example above:
- `minutes_covered = 10` (only 10 of 25 minutes covered)
- `balance_exhausted_at = startTime + 10 minutes`
- The ledger entry debits only 10 minutes (not 25)

This gives the client (e.g., a parental control app) the exact timestamp to lock the device.

---

## Technology Choices

### Why Python + FastAPI?

- **FastAPI & Pydantic v2**: Type hint validation catches malformed data before reaching business logic. Auto-generates OpenAPI / Swagger docs at `/docs`.
- **Built-in `sqlite3`**: Zero-dependency ACID database. Using shared-cache in-memory mode (`file:rewardbank_mem?mode=memory&cache=shared`) allows thread-safe concurrent access across FastAPI routes and Pytest workers.
- **HTTPBearer & FastAPI Dependencies**: Clean, declarative authentication and role authorization per endpoint (`require_parent`, `require_child`).
- **Pytest + TestClient**: Extremely fast, synchronous in-memory test runner executing all 40 tests in <0.5s.

---

## Authorization Model

| Endpoint | Parent | Child | Rationale |
|----------|--------|-------|-----------|
| Create task | ✅ | ❌ | Only parents assign tasks |
| Mark done | ❌ | ✅ | Only the assigned child can mark their own task done |
| Approve/Reject | ✅ | ❌ | Only parents control credits |
| Undo approval | ✅ | ❌ | Only parents can reverse mistakes |
| Report usage | ❌ | ✅ | Devices act on behalf of the child |
| View balance | ✅ | ✅* | Child can see only their own |
| View ledger | ✅ | ❌ | Audit trail is parent-only |

*Children can only view their own balance; parents can view any child in their family.

**Why can't children see the ledger?** The ledger contains audit information (corrections, reversals) that could confuse a child or create arguments. Parents get the full picture; children see their balance.

---

## Invariant Testing

The most important test in the suite proves the ledger invariant across a complex sequence:

1. Create 5 tasks with varying rewards (30, 20, 15, 45, 10)
2. Approve 3, reject 1, leave 1 pending
3. Report multiple usage sessions (some partial)
4. Undo one approval (causing balance to change)
5. Report more usage (partial coverage)
6. **Assert**: `SUM(signed ledger amounts) === GET /balance === latest balance_after`

A second invariant test specifically proves the invariant holds with a **negative balance** (undo after full spend).

---

## Worst-Case Scenario Design

The simulator's worst case ("Murphy's Law Day") was designed to stress-test every edge case simultaneously:

1. **Wrong approval → undo**: Tests the correction flow under pressure
2. **Negative balance**: Tests that the system correctly blocks usage
3. **Offline device → late session**: Tests out-of-order processing
4. **Duplicate submission**: Tests idempotency
5. **Recovery from negative**: Tests that earning back works correctly
6. **Invariant verification at every step**: Every checkpoint verifies the ledger

The scenario is deliberately adversarial — it's the kind of sequence that would expose race conditions, double-debiting, or accounting errors in a poorly designed system.
