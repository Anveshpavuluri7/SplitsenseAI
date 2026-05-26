"""
Cloudinary integration for receipt image storage.
Free tier: 25GB storage, 25GB bandwidth/month.
"""

import logging
import cloudinary
import cloudinary.uploader
from app.core.config import get_settings

logger = logging.getLogger("splitsenseai.services.cloud_storage")

settings = get_settings()

# Configure Cloudinary
if settings.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_to_cloudinary(image_bytes: bytes, folder: str = "receipts") -> str:
    """
    Upload an image to Cloudinary.

    Args:
        image_bytes: Raw image bytes.
        folder: Cloudinary folder path.

    Returns:
        Public URL of the uploaded image.
    """
    if not settings.CLOUDINARY_CLOUD_NAME:
        raise RuntimeError("Cloudinary not configured")

    result = cloudinary.uploader.upload(
        image_bytes,
        folder=f"splitsenseai/{folder}",
        resource_type="image",
        transformation=[
            {"quality": "auto:good", "fetch_format": "auto"},
        ],
    )

    url = result.get("secure_url", "")
    logger.info(f"Uploaded to Cloudinary: {url}")
    return url
