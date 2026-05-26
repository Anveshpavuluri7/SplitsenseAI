"""
Item and ItemAssignment ORM models.
Items are extracted from receipts. Assignments track per-user splits.
"""

import uuid

from sqlalchemy import String, Integer, Numeric, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str | None] = mapped_column(String(100))
    category_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    embedding: Mapped[dict | None] = mapped_column(JSON)  # cached embedding vector

    # Relationships
    receipt = relationship("Receipt", back_populates="items")
    assignments = relationship(
        "ItemAssignment", back_populates="item", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Item(id={self.id}, name={self.name}, price={self.price})>"


class ItemAssignment(Base):
    __tablename__ = "item_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    split_type: Mapped[str] = mapped_column(
        String(20), default="equal"  # equal | percentage | personal
    )
    share_value: Mapped[float | None] = mapped_column(Numeric(10, 4))  # percentage or fixed
    computed_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))  # final calculated $

    # Relationships
    item = relationship("Item", back_populates="assignments")
    user = relationship("User", back_populates="item_assignments")

    def __repr__(self) -> str:
        return f"<ItemAssignment(item={self.item_id}, user={self.user_id}, amount={self.computed_amount})>"
