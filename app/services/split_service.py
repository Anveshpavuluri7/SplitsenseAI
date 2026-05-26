"""
Bill splitting service.
Handles item assignment to users with equal/percentage/personal split types.
"""

import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.item import Item, ItemAssignment
from app.models.receipt import Receipt
from app.models.transaction import Transaction
from app.models.user import User

logger = logging.getLogger("splitsenseai.services.split")


class SplitService:
    """
    Computes bill splits for receipt items.
    Supports equal, percentage, and personal assignment types.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def split_receipt(
        self,
        receipt_id: uuid.UUID,
        assignments: list[dict],
        group_id: uuid.UUID | None = None,
    ) -> list[ItemAssignment]:
        """
        Split a receipt's items among users.

        Args:
            receipt_id: The receipt to split.
            assignments: List of dicts:
                [
                    {"item_id": ..., "user_id": ..., "split_type": "equal", "share_value": None},
                    {"item_id": ..., "user_id": ..., "split_type": "percentage", "share_value": 60},
                    ...
                ]

        Returns:
            List of created ItemAssignment objects.
        """
        # Group assignments by item
        item_assignments = {}
        for a in assignments:
            item_id = str(a["item_id"])
            if item_id not in item_assignments:
                item_assignments[item_id] = []
            item_assignments[item_id].append(a)

        created = []

        for item_id_str, item_assigns in item_assignments.items():
            item_id = uuid.UUID(item_id_str)

            # Get item price
            result = await self.db.execute(select(Item).where(Item.id == item_id))
            item = result.scalar_one_or_none()
            if not item:
                logger.warning(f"Item {item_id} not found, skipping")
                continue

            total_price = Decimal(str(item.price)) * item.quantity

            # Delete existing assignments for this item
            existing = await self.db.execute(
                select(ItemAssignment).where(ItemAssignment.item_id == item_id)
            )
            for old in existing.scalars().all():
                await self.db.delete(old)

            # Compute amounts based on split type
            computed = self._compute_split(total_price, item_assigns)

            for assign_data in computed:
                assignment = ItemAssignment(
                    item_id=item_id,
                    user_id=assign_data["user_id"],
                    split_type=assign_data["split_type"],
                    share_value=assign_data.get("share_value"),
                    computed_amount=float(assign_data["computed_amount"]),
                )
                self.db.add(assignment)
                created.append(assignment)

        await self.db.flush()

        # Create debt transactions for the group (use explicit group_id if provided,
        # fall back to receipt.group_id)
        receipt_result = await self.db.execute(select(Receipt).where(Receipt.id == receipt_id))
        receipt = receipt_result.scalar_one_or_none()
        effective_group_id = (receipt.group_id if receipt else None) or group_id
        if receipt and effective_group_id:
            await self._create_transactions(receipt, created, effective_group_id)

        logger.info(f"Created {len(created)} assignments for receipt {receipt_id}")
        return created

    async def _create_transactions(self, receipt: Receipt, assignments: list[ItemAssignment], group_id: uuid.UUID | None = None):
        """
        Create Transaction records from item assignments.
        Each non-payer assigned to an item owes that amount to the receipt uploader (payer).
        """
        from sqlalchemy import delete
        from app.models.transaction import Transaction

        # Clear existing transactions for this receipt to avoid duplicates on re-split
        await self.db.execute(
            delete(Transaction).where(Transaction.receipt_id == receipt.id)
        )

        effective_gid = group_id or receipt.group_id
        payer_id = receipt.uploaded_by
        for assignment in assignments:
            if assignment.user_id == payer_id:
                continue  # payer doesn't owe themselves
            if not assignment.computed_amount or assignment.computed_amount <= 0:
                continue
            txn = Transaction(
                group_id=effective_gid,
                from_user=assignment.user_id,
                to_user=payer_id,
                amount=float(assignment.computed_amount),
                receipt_id=receipt.id,
            )
            self.db.add(txn)

        await self.db.flush()

    @staticmethod
    def _compute_split(total_price: Decimal, assigns: list[dict]) -> list[dict]:
        """
        Compute the dollar amount each user owes for an item.

        Split types:
        - equal: divide evenly among all assigned users
        - percentage: each user pays their percentage of the item price
        - personal: entire item assigned to one user
        """
        n_users = len(assigns)

        if n_users == 0:
            return assigns

        split_type = assigns[0].get("split_type", "equal")

        if split_type == "personal":
            # Entire item goes to the single assigned user
            assigns[0]["computed_amount"] = total_price
            return assigns

        elif split_type == "percentage":
            # Each user pays their percentage
            for a in assigns:
                pct = Decimal(str(a.get("share_value", 0))) / Decimal("100")
                a["computed_amount"] = (total_price * pct).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            return assigns

        else:  # equal split
            per_person = (total_price / n_users).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

            # Handle rounding: give remainder to last person
            remainder = total_price - (per_person * n_users)

            for i, a in enumerate(assigns):
                a["computed_amount"] = per_person
                a["share_value"] = float(Decimal("100") / n_users)

            if remainder != 0 and assigns:
                assigns[-1]["computed_amount"] += remainder

            return assigns

    async def get_split(self, receipt_id: uuid.UUID) -> dict:
        """
        Get the current split state for a receipt.

        Returns:
            {
                "receipt_id": ...,
                "total": 25.47,
                "assignments": [...],
                "user_totals": {"alice": 12.74, "bob": 12.73}
            }
        """
        # Get receipt
        result = await self.db.execute(select(Receipt).where(Receipt.id == receipt_id))
        receipt = result.scalar_one_or_none()
        if not receipt:
            return {}

        # Get all items and their assignments
        items_result = await self.db.execute(
            select(Item).where(Item.receipt_id == receipt_id)
        )
        items = items_result.scalars().all()

        # Collect all unique user IDs across assignments
        all_user_ids = set()
        for item in items:
            for a in item.assignments:
                all_user_ids.add(a.user_id)

        # Resolve UUIDs → usernames in one query
        username_map: dict[str, str] = {}
        if all_user_ids:
            users_result = await self.db.execute(
                select(User).where(User.id.in_(all_user_ids))
            )
            for u in users_result.scalars().all():
                username_map[str(u.id)] = u.username

        all_assignments = []
        user_totals: dict[str, float] = {}

        for item in items:
            for assignment in item.assignments:
                uid = str(assignment.user_id)
                uname = username_map.get(uid, uid[:8])
                all_assignments.append({
                    "item_name": item.name,
                    "item_price": float(item.price),
                    "user_id": uid,
                    "username": uname,
                    "split_type": assignment.split_type,
                    "computed_amount": float(assignment.computed_amount or 0),
                })
                user_totals[uname] = user_totals.get(uname, 0) + float(assignment.computed_amount or 0)

        return {
            "receipt_id": str(receipt_id),
            "total": float(receipt.total_amount or 0),
            "assignments": all_assignments,
            "user_totals": user_totals,
        }
