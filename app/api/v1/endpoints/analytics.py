"""Analytics endpoints — spending insights."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/spending")
async def get_spending(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return {
        "category_spending": await service.get_category_spending(current_user.id),
        "store_spending": await service.get_store_spending(current_user.id),
    }


@router.get("/trends")
async def get_trends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return {"monthly_trends": await service.get_monthly_trends(current_user.id)}


@router.get("/anomalies")
async def get_anomalies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AnalyticsService(db)
    return {"anomalies": await service.detect_anomalies(current_user.id)}


@router.get("/insights")
async def get_insights(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Single endpoint returning all personal finance data for the Insights page."""
    service = AnalyticsService(db)
    return {
        "category_spending": await service.get_category_spending(current_user.id),
        "store_spending":     await service.get_store_spending(current_user.id),
        "monthly_trends":     await service.get_monthly_trends(current_user.id),
        "top_items":          await service.get_top_items(current_user.id),
        "month_comparison":   await service.get_month_comparison(current_user.id),
        "insight_cards":      await service.get_insights_summary(current_user.id),
        "anomalies":          await service.detect_anomalies(current_user.id),
    }
