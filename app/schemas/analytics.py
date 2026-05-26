"""
Analytics Pydantic schemas for spending insights.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel


class CategorySpending(BaseModel):
    """Spending breakdown by category."""
    category: str
    total: float
    percentage: float
    item_count: int


class StoreSpending(BaseModel):
    """Spending breakdown by store."""
    store_name: str
    total: float
    visit_count: int


class MonthlyTrend(BaseModel):
    """Monthly spending data point."""
    month: str  # "2026-04"
    total: float
    category_breakdown: dict[str, float]


class SpendingAnomaly(BaseModel):
    """Detected unusual spending pattern."""
    description: str
    amount: float
    expected_range: str
    severity: str  # low | medium | high


class AnalyticsResponse(BaseModel):
    """Full analytics response."""
    period: str
    total_spending: float
    category_spending: list[CategorySpending]
    store_spending: list[StoreSpending]
    monthly_trends: list[MonthlyTrend]
    anomalies: list[SpendingAnomaly]
