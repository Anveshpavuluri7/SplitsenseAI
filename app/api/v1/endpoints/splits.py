"""Split endpoints — assign items to users."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.split import SplitRequest, SplitResponse
from app.services.split_service import SplitService
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/splits", tags=["Splits"])


@router.post("/receipt/{receipt_id}")
async def split_receipt(
    receipt_id: uuid.UUID,
    data: SplitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SplitService(db)
    assignments = [a.model_dump() for a in data.assignments]
    await service.split_receipt(receipt_id, assignments, group_id=data.group_id)
    return await service.get_split(receipt_id)


@router.get("/receipt/{receipt_id}")
async def get_split(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SplitService(db)
    return await service.get_split(receipt_id)
