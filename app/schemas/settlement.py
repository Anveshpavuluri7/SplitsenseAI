"""
Settlement Pydantic schemas for debt resolution tracking.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class BalanceEntry(BaseModel):
    """A single balance between two users."""
    from_user_id: UUID
    from_username: str
    to_user_id: UUID
    to_username: str
    amount: float  # positive = from_user owes to_user


class GroupBalances(BaseModel):
    """Net balances for an entire group."""
    group_id: UUID
    group_name: str
    balances: list[BalanceEntry]
    total_unsettled: float


class SettleRequest(BaseModel):
    """Request to record a settlement payment."""
    from_user: UUID
    to_user: UUID
    amount: float


class SettlementResponse(BaseModel):
    """Response for a recorded settlement."""
    id: UUID
    group_id: UUID
    from_user: UUID
    to_user: UUID
    amount: float
    status: str
    settled_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SettlementHistory(BaseModel):
    """List of past settlements for a group."""
    group_id: UUID
    settlements: list[SettlementResponse]
