"""
EasyOCR wrapper for receipt text extraction.
Optimized for CPU-only execution.
"""

import easyocr
import numpy as np
import logging
from typing import Optional

logger = logging.getLogger("splitsenseai.ocr.extractor")

# Module-level reader (loaded once, reused)
_reader: Optional[easyocr.Reader] = None


def get_reader() -> easyocr.Reader:
    """
    Lazy-load and cache the EasyOCR reader.
    Loading takes ~2-5 seconds on first call.
    """
    global _reader
    if _reader is None:
        logger.info("Loading EasyOCR reader (CPU mode)...")
        _reader = easyocr.Reader(
            ["en"],
            gpu=False,  # CPU-only as per requirements
            model_storage_directory="ml/models",
            download_enabled=True,
        )
        logger.info("EasyOCR reader loaded successfully.")
    return _reader


class OCRExtractor:
    """
    Extracts text from preprocessed receipt images using EasyOCR.
    Returns text with bounding boxes and confidence scores.
    """

    def __init__(self, confidence_threshold: float = 0.4):
        self.confidence_threshold = confidence_threshold
        self.reader = get_reader()

    def extract(self, image: np.ndarray) -> list[dict]:
        """
        Run OCR on a preprocessed image.

        Args:
            image: Preprocessed numpy array (from ReceiptPreprocessor).

        Returns:
            List of detected text entries with bounding boxes and confidence:
            [
                {
                    "text": "Milk 2%",
                    "bbox": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]],
                    "confidence": 0.95,
                    "center_y": 150  # for vertical sorting
                },
                ...
            ]
        """
        logger.info("Running EasyOCR extraction...")

        results = self.reader.readtext(
            image,
            detail=1,
            paragraph=False,
            min_size=10,
            text_threshold=0.6,
            low_text=0.4,
            width_ths=0.7,  # merge nearby horizontal text
        )

        extracted = []
        for bbox, text, confidence in results:
            if confidence < self.confidence_threshold:
                logger.debug(f"Skipping low-confidence text: '{text}' ({confidence:.2f})")
                continue

            # Calculate center Y for vertical sorting (top-to-bottom reading order)
            center_y = sum(point[1] for point in bbox) / 4
            center_x = sum(point[0] for point in bbox) / 4

            extracted.append({
                "text": text.strip(),
                "bbox": bbox,
                "confidence": round(confidence, 4),
                "center_y": center_y,
                "center_x": center_x,
            })

        # Sort by vertical position (top to bottom)
        extracted.sort(key=lambda x: x["center_y"])

        logger.info(f"Extracted {len(extracted)} text entries (filtered {len(results) - len(extracted)} low-confidence)")
        return extracted

    def extract_raw_text(self, image: np.ndarray) -> str:
        """
        Extract text as a single string, preserving line order.
        Useful for NER and full-text analysis.
        """
        entries = self.extract(image)

        # Group entries by line (entries with similar Y coordinates)
        lines = self._group_into_lines(entries)

        # Build text string
        text_lines = []
        for line in lines:
            # Sort each line left-to-right
            line.sort(key=lambda x: x["center_x"])
            line_text = "  ".join(entry["text"] for entry in line)
            text_lines.append(line_text)

        return "\n".join(text_lines)

    @staticmethod
    def _group_into_lines(entries: list[dict], y_threshold: int = 15) -> list[list[dict]]:
        """
        Group text entries into lines based on Y-coordinate proximity.
        Entries within y_threshold pixels are considered same line.
        """
        if not entries:
            return []

        lines = []
        current_line = [entries[0]]

        for entry in entries[1:]:
            if abs(entry["center_y"] - current_line[-1]["center_y"]) < y_threshold:
                current_line.append(entry)
            else:
                lines.append(current_line)
                current_line = [entry]

        lines.append(current_line)
        return lines
