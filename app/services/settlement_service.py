"""
Settlement service.
Calculates net balances and optimizes settlement transactions
using the min-transactions algorithm.
"""

import uuid
import logging
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.transaction import Transaction
from app.models.settlement import Settlement
from app.models.user import User

logger = logging.getLogger("splitsenseai.services.settlement")


class SettlementService:
    """
    Calculates who owes whom and generates optimal settlement plan.
    Uses the min-transactions algorithm to minimize number of payments needed.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_balances(self, group_id: uuid.UUID) -> dict:
        """
        Calculate net balances for all users in a group.

        Returns:
            {
                "balances": [
                    {"from_user": ..., "to_user": ..., "amount": 15.50},
                    ...
                ],
                "total_unsettled": 45.00
            }
        """
        # Get all transactions for the group
        txn_result = await self.db.execute(
            select(Transaction).where(Transaction.group_id == group_id)
        )
        transactions = txn_result.scalars().all()

        # Get completed settlements
        settle_result = await self.db.execute(
            select(Settlement).where(
                and_(
                    Settlement.group_id == group_id,
                    Settlement.status == "completed",
                )
            )
        )
        settlements = settle_result.scalars().all()

        # Calculate net balances
        # Positive = user is owed money, Negative = user owes money
        net = defaultdict(Decimal)

        for txn in transactions:
            net[str(txn.from_user)] -= Decimal(str(txn.amount))
            net[str(txn.to_user)] += Decimal(str(txn.amount))

        # Subtract completed settlements
        for s in settlements:
            net[str(s.from_user)] += Decimal(str(s.amount))
            net[str(s.to_user)] -= Decimal(str(s.amount))

        # Optimize: compute minimum transactions needed
        optimal = self._min_transactions(net)

        total_unsettled = Decimal(str(sum(abs(v) for v in net.values()))) / 2

        # Resolve user IDs to usernames
        all_user_ids = {r["from_user"] for r in optimal} | {r["to_user"] for r in optimal}
        username_map: dict[str, str] = {}
        if all_user_ids:
            users_result = await self.db.execute(
                select(User).where(User.id.in_([uuid.UUID(uid) for uid in all_user_ids]))
            )
            for u in users_result.scalars().all():
                username_map[str(u.id)] = u.username

        for row in optimal:
            row["from_username"] = username_map.get(row["from_user"], row["from_user"][:8])
            row["to_username"]   = username_map.get(row["to_user"],   row["to_user"][:8])

        return {
            "balances": optimal,
            "total_unsettled": float(total_unsettled.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        }

    @staticmethod
    def _min_transactions(net_balances: dict[str, Decimal]) -> list[dict]:
        """
        Minimize the number of settlement transactions needed.

        Algorithm:
        1. Separate users into debtors (negative balance) and creditors (positive balance)
        2. Match the largest debtor with the largest creditor
        3. Settle the minimum of the two amounts
        4. Repeat until all balances are zero

        This greedy approach produces optimal or near-optimal results.
        """
        # Split into debtors and creditors
        debtors = []  # (user_id, abs_amount)
        creditors = []

        for user_id, balance in net_balances.items():
            if balance < -Decimal("0.01"):
                debtors.append([user_id, abs(balance)])
            elif balance > Decimal("0.01"):
                creditors.append([user_id, balance])

        # Sort by amount (largest first)
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)

        settlements = []

        while debtors and creditors:
            debtor_id, debt = debtors[0]
            creditor_id, credit = creditors[0]

            # Settle the minimum of the two
            settle_amount = min(debt, credit)

            settlements.append({
                "from_user": debtor_id,
                "to_user": creditor_id,
                "amount": float(settle_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
            })

            # Update remaining balances
            debtors[0][1] -= settle_amount
            creditors[0][1] -= settle_amount

            # Remove fully settled users
            if debtors[0][1] < Decimal("0.01"):
                debtors.pop(0)
            if creditors[0][1] < Decimal("0.01"):
                creditors.pop(0)

        return settlements

    async def record_settlement(
        self,
        group_id: uuid.UUID,
        from_user: uuid.UUID,
        to_user: uuid.UUID,
        amount: float,
    ) -> Settlement:
        """Record a settlement payment between two users."""
        settlement = Settlement(
            group_id=group_id,
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            status="completed",
            settled_at=datetime.now(timezone.utc),
        )
        self.db.add(settlement)
        await self.db.flush()

        logger.info(f"Settlement recorded: {from_user} → {to_user}: ${amount}")
        return settlement

    async def get_history(self, group_id: uuid.UUID) -> list[Settlement]:
        """Get settlement history for a group."""
        result = await self.db.execute(
            select(Settlement)
            .where(Settlement.group_id == group_id)
            .order_by(Settlement.settled_at.desc())
        )
        return list(result.scalars().all())
