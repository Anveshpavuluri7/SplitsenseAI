"""
Split Pydantic schemas for bill splitting requests/responses.
"""

from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class SplitAssignment(BaseModel):
    """Schema for assigning an item to a user with split rules."""
    item_id: UUID
    user_id: UUID
    split_type: str = Field(default="equal", pattern="^(equal|percentage|personal)$")
    share_value: Optional[float] = None  # percentage (0-100) or fixed amount


class SplitRequest(BaseModel):
    """Schema for splitting a receipt among users."""
    receipt_id: UUID
    group_id: Optional[UUID] = None   # group to charge transactions against
    assignments: list[SplitAssignment]


class AssignmentResponse(BaseModel):
    """Response for a computed assignment."""
    id: UUID
    item_id: UUID
    item_name: str
    user_id: UUID
    username: str
    split_type: str
    share_value: Optional[float] = None
    computed_amount: float

    model_config = {"from_attributes": True}


class SplitResponse(BaseModel):
    """Full split result for a receipt."""
    receipt_id: UUID
    store_name: Optional[str] = None
    total_amount: float
    assignments: list[AssignmentResponse]
    user_totals: dict[str, float]  # username -> total owed
