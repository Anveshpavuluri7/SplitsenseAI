"""Receipt endpoints — upload, get, list, correct items."""

import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks

logger = logging.getLogger("splitsenseai.api.receipts")
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sql_update

from app.db.session import get_db
from app.models.user import User
from app.models.item import Item
from app.models.receipt import Receipt
from app.schemas.receipt import ReceiptResponse, ReceiptListResponse, ItemUpdate, ItemResponse
from app.services.receipt_service import ReceiptService
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(prefix="/receipts", tags=["Receipts"])


async def _receipt_response(receipt: Receipt, db: AsyncSession) -> ReceiptResponse:
    result = await db.execute(select(Item).where(Item.receipt_id == receipt.id))
    items = result.scalars().all()
    return ReceiptResponse(
        id=receipt.id,
        uploaded_by=receipt.uploaded_by,
        group_id=receipt.group_id,
        store_name=receipt.store_name,
        receipt_date=receipt.receipt_date,
        total_amount=receipt.total_amount,
        image_path=receipt.image_path,
        status=receipt.status,
        created_at=receipt.created_at,
        items=[ItemResponse.model_validate(i) for i in items],
    )


@router.post("/upload", response_model=ReceiptResponse, status_code=201)
async def upload_receipt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    group_id: uuid.UUID = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/bmp"]:
        raise HTTPException(status_code=400, detail="Unsupported image format")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 10MB)")

    # Create receipt record immediately — return to client right away
    from app.models.receipt import Receipt as ReceiptModel
    receipt = ReceiptModel(
        uploaded_by=current_user.id,
        group_id=group_id,
        image_path=None,
        status="processing",
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)

    # Run OCR + categorization in background
    background_tasks.add_task(process_receipt_background, str(receipt.id), image_bytes, str(current_user.id))

    return await _receipt_response(receipt, db)


async def process_receipt_background(receipt_id: str, image_bytes: bytes, user_id: str):
    """Run full OCR pipeline in background so upload returns instantly."""
    from app.db.session import async_session_factory
    from app.models.receipt import Receipt as ReceiptModel
    from sqlalchemy import select as _select

    async with async_session_factory() as db:
        service = ReceiptService(db)
        result = await db.execute(_select(ReceiptModel).where(ReceiptModel.id == uuid.UUID(receipt_id)))
        receipt = result.scalar_one_or_none()
        if not receipt:
            return

        try:
            from ml.ocr.gemini_extractor import extract_receipt
            from app.models.item import Item
            from datetime import datetime

            parsed = await asyncio.to_thread(extract_receipt, image_bytes)

            receipt.store_name   = parsed["store_name"]
            receipt.raw_ocr_text = parsed["raw_text"]
            receipt.total_amount = parsed["total"]

            if parsed["receipt_date"]:
                try:
                    receipt.receipt_date = datetime.strptime(parsed["receipt_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            for item_data in parsed["items"]:
                db.add(Item(
                    receipt_id=receipt.id,
                    name=item_data["name"],
                    price=item_data["price"],
                    quantity=item_data.get("quantity", 1),
                ))

            # Upload image to Cloudinary
            try:
                from app.core.config import get_settings as _get_settings
                import cloudinary
                import cloudinary.uploader

                _s = _get_settings()
                cloudinary.config(
                    cloud_name=_s.CLOUDINARY_CLOUD_NAME.strip(),
                    api_key=_s.CLOUDINARY_API_KEY.strip(),
                    api_secret=_s.CLOUDINARY_API_SECRET.strip(),
                )
                upload_result = await asyncio.to_thread(
                    cloudinary.uploader.upload,
                    image_bytes,
                    folder="splitsenseai/receipts",
                    resource_type="image",
                    public_id=receipt_id,
                )
                receipt.image_path = upload_result.get("secure_url")
                logger.info(f"Uploaded receipt image to Cloudinary: {receipt.image_path}")
            except Exception as cdn_err:
                logger.warning(f"Cloudinary upload failed (non-fatal): {cdn_err}")

            receipt.status = "ready"
        except Exception as e:
            receipt.status = "error"
            receipt.raw_ocr_text = f"ERROR: {e}"
            logger.error(f"Groq extraction failed for receipt {receipt_id}: {e}")

        await db.commit()

        if receipt.status == "ready":
            await service.categorize_items(uuid.UUID(receipt_id))
            await db.commit()


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await _receipt_response(receipt, db)


@router.delete("/{receipt_id}", status_code=204)
async def delete_receipt(
    receipt_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await service.delete_receipt(receipt_id)
    await db.commit()


@router.patch("/{receipt_id}/items/{item_id}", response_model=ItemResponse)
async def update_item(
    receipt_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipt = await service.get_receipt(receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if receipt.uploaded_by != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.receipt_id == receipt_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.name is not None:
        item.name = payload.name
    if payload.price is not None:
        item.price = payload.price
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.category is not None:
        item.category = payload.category

    await db.commit()

    # Recalculate receipt total from all current items using a direct SQL UPDATE
    all_items_result = await db.execute(select(Item).where(Item.receipt_id == receipt_id))
    all_items = all_items_result.scalars().all()
    new_total = round(sum(float(i.price) * i.quantity for i in all_items), 2)
    await db.execute(sql_update(Receipt).where(Receipt.id == receipt_id).values(total_amount=new_total))
    await db.commit()

    await db.refresh(item)
    return ItemResponse.model_validate(item)


@router.get("/", response_model=ReceiptListResponse)
async def list_receipts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ReceiptService(db)
    receipts, total = await service.list_receipts(current_user.id, page, per_page)
    return ReceiptListResponse(
        receipts=[await _receipt_response(r, db) for r in receipts],
        total=total, page=page, per_page=per_page,
    )
