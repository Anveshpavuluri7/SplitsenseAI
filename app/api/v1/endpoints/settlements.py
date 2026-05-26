"""Settlement endpoints — balances, settle, history."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.settlement import SettleRequest, SettlementResponse, GroupBalances
from app.services.settlement_service import SettlementService
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/settlements", tags=["Settlements"])


@router.get("/group/{group_id}/balances")
async def get_balances(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SettlementService(db)
    return await service.calculate_balances(group_id)


@router.post("/group/{group_id}/settle", response_model=SettlementResponse)
async def settle(
    group_id: uuid.UUID,
    data: SettleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SettlementService(db)
    settlement = await service.record_settlement(group_id, data.from_user, data.to_user, data.amount)
    return SettlementResponse.model_validate(settlement)


@router.get("/group/{group_id}/history")
async def settlement_history(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SettlementService(db)
    settlements = await service.get_history(group_id)
    return [SettlementResponse.model_validate(s) for s in settlements]
