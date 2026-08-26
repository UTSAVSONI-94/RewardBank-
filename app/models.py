"""Pydantic models for request/response validation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────

class UserRole(str, Enum):
    PARENT = "parent"
    CHILD = "child"


class TaskStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNDONE = "undone"


class LedgerEntryType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    REVERSAL = "reversal"


class LedgerSourceType(str, Enum):
    TASK_APPROVAL = "task_approval"
    USAGE_SESSION = "usage_session"
    APPROVAL_REVERSAL = "approval_reversal"


class UsageSessionStatus(str, Enum):
    PROCESSED = "processed"
    REJECTED = "rejected"


# ─── User ────────────────────────────────────────────────────

class User(BaseModel):
    id: str
    family_id: str
    name: str
    role: UserRole
    token: str


# ─── Task ────────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    child_id: str = Field(..., alias="childId")
    title: str
    reward_minutes: int = Field(..., gt=0, alias="rewardMinutes")

    model_config = {"populate_by_name": True}


class TaskResponse(BaseModel):
    id: str
    family_id: str = Field(alias="familyId")
    child_id: str = Field(alias="childId")
    created_by: str = Field(alias="createdBy")
    title: str
    reward_minutes: int = Field(alias="rewardMinutes")
    status: TaskStatus
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ─── Ledger ──────────────────────────────────────────────────

class LedgerEntryResponse(BaseModel):
    id: int
    child_id: str = Field(alias="childId")
    entry_type: LedgerEntryType = Field(alias="entryType")
    amount: int
    balance_after: int = Field(alias="balanceAfter")
    source_type: LedgerSourceType = Field(alias="sourceType")
    source_id: str = Field(alias="sourceId")
    description: Optional[str] = None
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ─── Usage Session ───────────────────────────────────────────

class UsageSessionInput(BaseModel):
    app_id: str = Field(..., alias="appId")
    start_time: str = Field(..., alias="startTime")
    end_time: str = Field(..., alias="endTime")

    model_config = {"populate_by_name": True}


class UsageBatchRequest(BaseModel):
    sessions: list[UsageSessionInput]


class UsageSessionResult(BaseModel):
    session_id: str = Field(alias="sessionId")
    app_id: str = Field(alias="appId")
    duration_minutes: int = Field(alias="durationMinutes")
    minutes_covered: int = Field(alias="minutesCovered")
    balance_exhausted_at: Optional[str] = Field(None, alias="balanceExhaustedAt")
    status: UsageSessionStatus
    deduplicated: bool

    model_config = {"populate_by_name": True}


class UsageBatchResponse(BaseModel):
    results: list[UsageSessionResult]


# ─── API Responses ───────────────────────────────────────────

class BalanceResponse(BaseModel):
    child_id: str = Field(alias="childId")
    balance: int
    as_of: str = Field(alias="asOf")

    model_config = {"populate_by_name": True}


class LedgerResponse(BaseModel):
    child_id: str = Field(alias="childId")
    entries: list[LedgerEntryResponse]
    current_balance: int = Field(alias="currentBalance")
    computed_balance: int = Field(alias="computedBalance")
    invariant_holds: bool = Field(alias="invariantHolds")

    model_config = {"populate_by_name": True}


class UndoApprovalResponse(BaseModel):
    task: TaskResponse
    reversal: LedgerEntryResponse
    warning: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
