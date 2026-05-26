"""
User Pydantic schemas for request/response validation.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# --- Request Schemas ---

class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


# --- Response Schemas ---

class UserResponse(BaseModel):
    """Schema for user data in API responses."""
    id: UUID
    email: str
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
