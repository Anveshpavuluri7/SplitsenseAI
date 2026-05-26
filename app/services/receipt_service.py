"""
Receipt processing service.
Orchestrates the OCR pipeline: upload → preprocess → extract → parse → categorize → save.
"""

import uuid
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.receipt import Receipt
from app.models.item import Item
from ml.ocr.preprocessor import ReceiptPreprocessor
from ml.ocr.extractor import OCRExtractor
from ml.ocr.parser import ReceiptParser

logger = logging.getLogger("splitsenseai.services.receipt")


class ReceiptService:
    """Handles receipt upload, OCR processing, and data persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.preprocessor = ReceiptPreprocessor()
        self.extractor = OCRExtractor()
        self.parser = ReceiptParser()

    async def process_receipt(
        self,
        image_bytes: bytes,
        user_id: uuid.UUID,
        group_id: uuid.UUID | None = None,
        image_url: str | None = None,
    ) -> Receipt:
        """
        Full receipt processing pipeline.

        Args:
            image_bytes: Raw image bytes from upload.
            user_id: Uploading user's ID.
            group_id: Optional group to associate receipt with.
            image_url: Cloudinary URL after upload.

        Returns:
            Saved Receipt ORM object with extracted items.
        """
        # Create receipt record (status=processing)
        receipt = Receipt(
            uploaded_by=user_id,
            group_id=group_id,
            image_path=image_url,
            status="processing",
        )
        self.db.add(receipt)
        await self.db.flush()  # get the ID

        try:
            # Step 1: Preprocess image
            logger.info(f"Processing receipt {receipt.id}...")
            preprocessed = self.preprocessor.preprocess(image_bytes)

            # Step 2: OCR extraction
            ocr_entries = self.extractor.extract(preprocessed)
            raw_text = self.extractor.extract_raw_text(preprocessed)

            # Step 3: Parse structured data
            parsed = self.parser.parse(ocr_entries)

            # Step 4: Update receipt with extracted data
            receipt.store_name = parsed["store_name"]
            receipt.raw_ocr_text = raw_text
            receipt.total_amount = parsed["total"]

            # Parse date
            if parsed["receipt_date"]:
                try:
                    receipt.receipt_date = datetime.strptime(parsed["receipt_date"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Step 5: Create item records
            for item_data in parsed["items"]:
                item = Item(
                    receipt_id=receipt.id,
                    name=item_data["name"],
                    price=item_data["price"],
                    quantity=item_data.get("quantity", 1),
                )
                self.db.add(item)

            receipt.status = "ready"
            logger.info(
                f"Receipt {receipt.id} processed: store={receipt.store_name}, "
                f"items={len(parsed['items'])}, total={receipt.total_amount}"
            )

        except Exception as e:
            receipt.status = "error"
            receipt.raw_ocr_text = f"ERROR: {str(e)}"
            logger.error(f"Receipt processing failed: {e}")

        await self.db.flush()
        return receipt

    async def categorize_items(self, receipt_id: uuid.UUID):
        """
        Categorize all items in a receipt using ML.
        Called after initial processing or on demand.
        """
        from ml.categorizer.zero_shot import ZeroShotCategorizer
        from ml.categorizer.classifier import TrainedClassifier

        # Get items
        result = await self.db.execute(
            select(Item).where(Item.receipt_id == receipt_id)
        )
        items = result.scalars().all()

        if not items:
            return

        # Try trained classifier first, fall back to zero-shot
        trained = TrainedClassifier()
        if trained.is_ready:
            categorizer = trained
            logger.info("Using trained classifier for categorization")
        else:
            categorizer = ZeroShotCategorizer()
            logger.info("Using zero-shot classifier for categorization")

        for item in items:
            try:
                if trained.is_ready:
                    result = trained.predict(item.name)
                else:
                    result = categorizer.categorize(item.name)

                item.category = result["category"]
                item.category_confidence = result["confidence"]
            except Exception as e:
                logger.error(f"Failed to categorize item '{item.name}': {e}")
                item.category = "Miscellaneous"
                item.category_confidence = 0.0

        await self.db.flush()
        logger.info(f"Categorized {len(items)} items for receipt {receipt_id}")

    async def delete_receipt(self, receipt_id: uuid.UUID) -> bool:
        """Delete a receipt and its items. Returns False if not found."""
        result = await self.db.execute(select(Receipt).where(Receipt.id == receipt_id))
        receipt = result.scalar_one_or_none()
        if not receipt:
            return False
        await self.db.delete(receipt)
        await self.db.flush()
        return True

    async def get_receipt(self, receipt_id: uuid.UUID) -> Receipt | None:
        """Get a receipt by ID with items loaded."""
        result = await self.db.execute(
            select(Receipt).where(Receipt.id == receipt_id)
        )
        return result.scalar_one_or_none()

    async def list_receipts(
        self, user_id: uuid.UUID, page: int = 1, per_page: int = 20
    ) -> tuple[list[Receipt], int]:
        """List receipts for a user with pagination."""
        # Count total
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count(Receipt.id)).where(Receipt.uploaded_by == user_id)
        )
        total = count_result.scalar()

        # Fetch page
        offset = (page - 1) * per_page
        result = await self.db.execute(
            select(Receipt)
            .where(Receipt.uploaded_by == user_id)
            .order_by(Receipt.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        receipts = result.scalars().all()

        return list(receipts), total
