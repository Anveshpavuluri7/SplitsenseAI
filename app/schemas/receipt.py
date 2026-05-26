"""
Receipt Pydantic schemas for request/response validation.
"""

from datetime import datetime, date
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


# --- Item Schemas ---

class ItemResponse(BaseModel):
    """Schema for an extracted item."""
    id: UUID
    name: str
    price: float
    quantity: int
    category: Optional[str] = None
    category_confidence: Optional[float] = None

    model_config = {"from_attributes": True}


class ItemUpdate(BaseModel):
    """Schema for correcting item data."""
    name: Optional[str] = None
    price: Optional[float] = None
    quantity: Optional[int] = None
    category: Optional[str] = None


# --- Receipt Schemas ---

class ReceiptResponse(BaseModel):
    """Schema for receipt data in API responses."""
    id: UUID
    uploaded_by: UUID
    group_id: Optional[UUID] = None
    store_name: Optional[str] = None
    receipt_date: Optional[date] = None
    total_amount: Optional[float] = None
    image_path: Optional[str] = None
    status: str
    items: list[ItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptListResponse(BaseModel):
    """Paginated receipt list response."""
    receipts: list[ReceiptResponse]
    total: int
    page: int
    per_page: int


class OCRResultResponse(BaseModel):
    """Raw OCR extraction result before saving."""
    store_name: Optional[str] = None
    receipt_date: Optional[str] = None
    items: list[dict] = []
    total: Optional[float] = None
    raw_text: str
    confidence: float
