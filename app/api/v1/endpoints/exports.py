"""Export endpoints — Excel download."""

import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.db.session import get_db
from app.models.user import User
from app.services.export_service import ExportService
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/excel")
async def export_excel(
    group_id: uuid.UUID = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExportService(db)
    excel_bytes = await service.generate_excel(current_user.id, group_id)

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=splitsenseai_report.xlsx"},
    )
