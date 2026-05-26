"""
Analytics service.
Provides spending insights, trends, anomaly detection, and personal finance summaries.
"""

import uuid
import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.models.receipt import Receipt
from app.models.item import Item

logger = logging.getLogger("splitsenseai.services.analytics")


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_category_spending(self, user_id: uuid.UUID) -> list[dict]:
        result = await self.db.execute(
            select(
                Item.category,
                func.sum(Item.price * Item.quantity).label("total"),
                func.count(Item.id).label("count"),
            )
            .join(Receipt, Item.receipt_id == Receipt.id)
            .where(Receipt.uploaded_by == user_id)
            .group_by(Item.category)
            .order_by(func.sum(Item.price * Item.quantity).desc())
        )
        rows = result.all()
        grand_total = sum(float(row.total or 0) for row in rows)
        return [
            {
                "category": row.category or "Uncategorized",
                "total": round(float(row.total or 0), 2),
                "percentage": round(float(row.total or 0) / grand_total * 100, 1) if grand_total > 0 else 0,
                "item_count": row.count,
            }
            for row in rows
        ]

    async def get_store_spending(self, user_id: uuid.UUID) -> list[dict]:
        result = await self.db.execute(
            select(
                Receipt.store_name,
                func.sum(Receipt.total_amount).label("total"),
                func.count(Receipt.id).label("visits"),
            )
            .where(Receipt.uploaded_by == user_id)
            .group_by(Receipt.store_name)
            .order_by(func.sum(Receipt.total_amount).desc())
        )
        return [
            {"store_name": r.store_name or "Unknown", "total": round(float(r.total or 0), 2), "visit_count": r.visits}
            for r in result.all()
        ]

    async def get_monthly_trends(self, user_id: uuid.UUID) -> list[dict]:
        month_expr = func.to_char(Receipt.receipt_date, text("'YYYY-MM'"))
        result = await self.db.execute(
            select(month_expr.label("month"), func.sum(Receipt.total_amount).label("total"))
            .where(Receipt.uploaded_by == user_id)
            .where(Receipt.receipt_date.isnot(None))
            .group_by(month_expr)
            .order_by(month_expr)
        )
        return [{"month": r.month, "total": round(float(r.total or 0), 2)} for r in result.all()]

    async def detect_anomalies(self, user_id: uuid.UUID) -> list[dict]:
        result = await self.db.execute(
            select(Receipt.total_amount).where(Receipt.uploaded_by == user_id).where(Receipt.total_amount.isnot(None))
        )
        amounts = [float(r[0]) for r in result.all()]
        if len(amounts) < 5:
            return []
        import numpy as np
        mean, std = np.mean(amounts), np.std(amounts)
        if std == 0:
            return []
        anomalies = []
        for a in amounts:
            z = (a - mean) / std
            if abs(z) > 2:
                anomalies.append({
                    "description": f"Unusual spending: ${a:.2f} (z={z:.1f})",
                    "amount": a,
                    "expected_range": f"${mean-2*std:.2f}-${mean+2*std:.2f}",
                    "severity": "high" if abs(z) > 3 else "medium",
                })
        return anomalies

    async def get_top_items(self, user_id: uuid.UUID, limit: int = 10) -> list[dict]:
        """Most frequently bought items across all receipts."""
        result = await self.db.execute(
            select(
                Item.name,
                Item.category,
                func.count(Item.id).label("frequency"),
                func.sum(Item.price * Item.quantity).label("total_spent"),
            )
            .join(Receipt, Item.receipt_id == Receipt.id)
            .where(Receipt.uploaded_by == user_id)
            .group_by(Item.name, Item.category)
            .order_by(func.count(Item.id).desc())
            .limit(limit)
        )
        return [
            {
                "name": r.name,
                "category": r.category or "Uncategorized",
                "frequency": r.frequency,
                "total_spent": round(float(r.total_spent or 0), 2),
            }
            for r in result.all()
        ]

    async def get_month_comparison(self, user_id: uuid.UUID) -> dict:
        """Compare spending in the current month vs the previous month."""
        today = date.today()
        current_start = today.replace(day=1)
        prev_end = current_start - timedelta(days=1)
        prev_start = prev_end.replace(day=1)

        async def _month_total(start: date, end: date) -> float:
            res = await self.db.execute(
                select(func.sum(Receipt.total_amount))
                .where(Receipt.uploaded_by == user_id)
                .where(Receipt.receipt_date >= start)
                .where(Receipt.receipt_date <= end)
            )
            return float(res.scalar() or 0)

        current = await _month_total(current_start, today)
        previous = await _month_total(prev_start, prev_end)
        change_pct = round((current - previous) / previous * 100, 1) if previous > 0 else 0

        return {
            "current_month": round(current, 2),
            "previous_month": round(previous, 2),
            "change_pct": change_pct,
            "current_label": current_start.strftime("%B %Y"),
            "previous_label": prev_start.strftime("%B %Y"),
        }

    async def get_insights_summary(self, user_id: uuid.UUID) -> list[dict]:
        """
        Generate a list of natural-language insight cards from the user's data.
        Each card has: type, icon, title, detail.
        """
        cat_spending = await self.get_category_spending(user_id)
        store_spending = await self.get_store_spending(user_id)
        month_comp = await self.get_month_comparison(user_id)
        anomalies = await self.detect_anomalies(user_id)
        top_items = await self.get_top_items(user_id, limit=1)

        insights = []

        # Top spending category
        if cat_spending:
            top = cat_spending[0]
            insights.append({
                "type": "category",
                "icon": "🏷️",
                "title": f"{top['category']} is your biggest category",
                "detail": f"${top['total']:.2f} spent — {top['percentage']}% of total",
                "value": top["percentage"],
                "unit": "%",
            })

        # Favourite store
        if store_spending:
            top = store_spending[0]
            insights.append({
                "type": "store",
                "icon": "🏪",
                "title": f"{top['store_name']} is your go-to store",
                "detail": f"{top['visit_count']} visit{'s' if top['visit_count'] != 1 else ''} · ${top['total']:.2f} total",
                "value": top["visit_count"],
                "unit": "visits",
            })

        # Month-over-month change
        if month_comp["previous_month"] > 0:
            arrow = "↑" if month_comp["change_pct"] > 0 else "↓"
            direction = "more" if month_comp["change_pct"] > 0 else "less"
            insights.append({
                "type": "trend",
                "icon": "📅",
                "title": f"{arrow} {abs(month_comp['change_pct'])}% {direction} than last month",
                "detail": f"{month_comp['current_label']}: ${month_comp['current_month']:.2f}  ·  {month_comp['previous_label']}: ${month_comp['previous_month']:.2f}",
                "value": month_comp["change_pct"],
                "unit": "%",
            })
        elif month_comp["current_month"] > 0:
            insights.append({
                "type": "trend",
                "icon": "📅",
                "title": f"First month tracked: {month_comp['current_label']}",
                "detail": f"${month_comp['current_month']:.2f} spent so far",
                "value": month_comp["current_month"],
                "unit": "$",
            })

        # Most-bought item
        if top_items:
            item = top_items[0]
            insights.append({
                "type": "item",
                "icon": "🛒",
                "title": f"'{item['name']}' is your most-bought item",
                "detail": f"Bought {item['frequency']} times · ${item['total_spent']:.2f} total · {item['category']}",
                "value": item["frequency"],
                "unit": "times",
            })

        # Anomaly alert
        if anomalies:
            high = [a for a in anomalies if a["severity"] == "high"]
            insights.append({
                "type": "anomaly",
                "icon": "⚠️",
                "title": f"{len(anomalies)} unusually high receipt{'s' if len(anomalies) != 1 else ''} detected",
                "detail": f"Expected range: {anomalies[0]['expected_range']}" + (f"  ·  {len(high)} flagged as high" if high else ""),
                "value": len(anomalies),
                "unit": "flagged",
            })

        return insights
