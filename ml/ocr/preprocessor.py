"""
Image Preprocessor for receipt photos.
Optimized for mobile phone uploads — handles rotation, noise, poor lighting.
Uses OpenCV for CPU-only processing.
"""

import cv2
import numpy as np
from PIL import Image
import io
import logging

logger = logging.getLogger("splitsenseai.ocr.preprocessor")


class ReceiptPreprocessor:
    """
    Preprocesses receipt images for optimal OCR accuracy.
    Pipeline: resize → grayscale → denoise → adaptive threshold → deskew
    """

    # Target width for processing (maintains aspect ratio)
    TARGET_WIDTH = 800

    @staticmethod
    def preprocess(image_bytes: bytes) -> np.ndarray:
        """
        Full preprocessing pipeline for a receipt image.

        Args:
            image_bytes: Raw image bytes from upload.

        Returns:
            Preprocessed image as numpy array (ready for OCR).
        """
        # Decode image — fix EXIF rotation from phone cameras first
        pil_img = Image.open(io.BytesIO(image_bytes))
        from PIL import ImageOps
        pil_img = ImageOps.exif_transpose(pil_img)
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG")
        nparr = np.frombuffer(buf.getvalue(), np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Could not decode image. Ensure the file is a valid image.")

        logger.info(f"Original image size: {img.shape[1]}x{img.shape[0]}")

        # Step 1: Resize (maintain aspect ratio, optimize for mobile photos)
        img = ReceiptPreprocessor._resize(img)

        # Step 2: Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Step 3: Denoise — use small search window for speed on CPU
        denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=11)

        # Step 4: Enhance contrast (CLAHE — handles uneven lighting)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Step 5: Adaptive threshold (handles shadows and gradients)
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 11
        )

        # Step 6: Deskew (correct phone camera tilt)
        deskewed = ReceiptPreprocessor._deskew(binary)

        logger.info(f"Preprocessed image size: {deskewed.shape[1]}x{deskewed.shape[0]}")
        return deskewed

    @staticmethod
    def preprocess_for_display(image_bytes: bytes) -> np.ndarray:
        """
        Light preprocessing for display purposes (not OCR).
        Just resize and auto-orient.
        """
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image.")
        return ReceiptPreprocessor._resize(img, target_width=800)

    @staticmethod
    def _resize(img: np.ndarray, target_width: int = None) -> np.ndarray:
        """Resize image maintaining aspect ratio."""
        target_width = target_width or ReceiptPreprocessor.TARGET_WIDTH
        h, w = img.shape[:2]

        if w <= target_width:
            return img

        ratio = target_width / w
        new_h = int(h * ratio)
        return cv2.resize(img, (target_width, new_h), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _deskew(img: np.ndarray) -> np.ndarray:
        """
        Deskew a binary image by detecting the dominant text angle.
        Uses Hough line detection to find the skew angle.
        """
        try:
            # Detect edges
            edges = cv2.Canny(img, 50, 150, apertureSize=3)

            # Detect lines using probabilistic Hough transform
            lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, threshold=100,
                minLineLength=100, maxLineGap=10
            )

            if lines is None or len(lines) == 0:
                return img

            # Calculate median angle of detected lines
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                # Only consider near-horizontal lines (within 15 degrees)
                if abs(angle) < 15:
                    angles.append(angle)

            if not angles:
                return img

            median_angle = np.median(angles)

            # Only correct if skew is significant (> 0.5 degrees)
            if abs(median_angle) < 0.5:
                return img

            logger.info(f"Deskewing by {median_angle:.2f} degrees")

            # Rotate image to correct skew
            h, w = img.shape[:2]
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            rotated = cv2.warpAffine(
                img, rotation_matrix, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            return rotated

        except Exception as e:
            logger.warning(f"Deskew failed, returning original: {e}")
            return img

    @staticmethod
    def compress_for_upload(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
        """
        Compress an image for Cloudinary upload.
        Optimized for mobile — reduces file size while preserving text readability.

        Args:
            image_bytes: Raw image bytes.
            max_size_kb: Maximum file size in KB.

        Returns:
            Compressed JPEG bytes.
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Auto-orient based on EXIF data (common with phone cameras)
        from PIL import ImageOps
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed (handles PNG with alpha)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large
        max_dim = 2000
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Compress with quality reduction until under max size
        quality = 85
        while quality > 20:
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            if buffer.tell() <= max_size_kb * 1024:
                return buffer.getvalue()
            quality -= 10

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=20, optimize=True)
        return buffer.getvalue()
