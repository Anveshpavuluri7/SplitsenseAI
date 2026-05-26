"""
Receipt ORM model.
Stores uploaded receipt metadata and OCR results.
"""

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, DateTime, Date, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id")
    )
    store_name: Mapped[str | None] = mapped_column(String(300))
    receipt_date: Mapped[date | None] = mapped_column(Date)
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    image_path: Mapped[str | None] = mapped_column(String(500))  # Cloudinary URL
    raw_ocr_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="processing"  # processing | ready | error
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    uploader = relationship("User", back_populates="receipts")
    group = relationship("Group", back_populates="receipts")
    items = relationship("Item", back_populates="receipt", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Receipt(id={self.id}, store={self.store_name}, status={self.status})>"
