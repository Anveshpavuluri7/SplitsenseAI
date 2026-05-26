"""
Group Pydantic schemas for request/response validation.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


# --- Request Schemas ---

class GroupCreate(BaseModel):
    """Schema for creating a new group."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)


class AddMember(BaseModel):
    """Schema for adding a member to a group."""
    user_id: UUID
    role: str = Field(default="member", pattern="^(admin|member)$")


# --- Response Schemas ---

class MemberResponse(BaseModel):
    """Schema for a group member."""
    id: UUID
    user_id: UUID
    username: str
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    """Schema for group data in API responses."""
    id: UUID
    name: str
    description: Optional[str] = None
    created_by: UUID
    members: list[MemberResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupListResponse(BaseModel):
    """List of groups the user belongs to."""
    groups: list[GroupResponse]
