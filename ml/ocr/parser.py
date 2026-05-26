"""
Receipt parser — converts raw OCR output into structured data.
Extracts store name, date, items with prices, and total.
Uses regex patterns and spatial analysis of bounding boxes.
"""

import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("splitsenseai.ocr.parser")


class ReceiptParser:
    """
    Parses raw OCR text entries into structured receipt data.
    Uses regex patterns for price/date extraction and spatial grouping for items.
    """

    # Price patterns: $12.99, 12.99, $1,234.56
    PRICE_PATTERN = re.compile(r'\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})\b')

    # Date patterns: MM/DD/YYYY, MM-DD-YYYY, YYYY-MM-DD, MM/DD/YY
    DATE_PATTERNS = [
        re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'),
        re.compile(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})'),
        re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2})\b'),
    ]

    # Total indicators
    TOTAL_KEYWORDS = [
        "total", "grand total", "amount due", "balance due",
        "subtotal", "sub total", "net total", "sum",
    ]

    # Lines to skip (headers, footers, non-item text)
    SKIP_PATTERNS = [
        re.compile(r'(thank\s*you|visa|mastercard|debit|credit|change\s*due|cash)', re.IGNORECASE),
        re.compile(r'(tel|phone|fax|www\.|http|survey|feedback|\.com)', re.IGNORECASE),
        re.compile(r'^\s*\d{3}[-.]?\d{3}[-.]?\d{4}\s*$'),   # phone numbers
        re.compile(r'^\s*#?\d{5,}\s*$'),                      # long numeric codes alone
        re.compile(r'(tax\s*id|ref\s*#|trans\s*id|terminal|validation|payment\s*service|aid\s*[a-z])', re.IGNORECASE),
        re.compile(r'(scan\s*to|qr\s*code|member|signature|appr#|visa\s*credit)', re.IGNORECASE),
    ]

    # Barcode / product code pattern to strip from item names
    BARCODE_PATTERN = re.compile(r'\b\d{6,}\b')

    def parse(self, ocr_entries: list[dict]) -> dict:
        """
        Parse OCR entries into structured receipt data.

        Args:
            ocr_entries: List from OCRExtractor.extract()

        Returns:
            {
                "store_name": "Walmart",
                "receipt_date": "2026-04-27",
                "items": [{"name": "Milk 2%", "price": 3.99, "quantity": 1}, ...],
                "total": 25.47,
                "raw_text": "full text...",
                "confidence": 0.87
            }
        """
        if not ocr_entries:
            return {"store_name": None, "receipt_date": None, "items": [], "total": None, "raw_text": "", "confidence": 0}

        # Build full text for analysis
        all_texts = [e["text"] for e in ocr_entries]
        raw_text = "\n".join(all_texts)

        # Extract components
        store_name = self._extract_store_name(ocr_entries)
        receipt_date = self._extract_date(raw_text)
        items = self._extract_items(ocr_entries)
        total = self._extract_total(ocr_entries)

        # Calculate average confidence
        confidences = [e["confidence"] for e in ocr_entries]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Validate: total should roughly match sum of items
        items_sum = sum(item["price"] * item["quantity"] for item in items)
        if total and items and abs(total - items_sum) / max(total, 1) > 0.3:
            logger.warning(
                f"Total mismatch: extracted total={total}, items sum={items_sum:.2f}. "
                "Consider manual review."
            )

        result = {
            "store_name": store_name,
            "receipt_date": receipt_date,
            "items": items,
            "total": total or (round(items_sum, 2) if items else None),
            "raw_text": raw_text,
            "confidence": round(avg_confidence, 4),
        }

        logger.info(
            f"Parsed receipt: store={store_name}, date={receipt_date}, "
            f"items={len(items)}, total={result['total']}"
        )
        return result

    def _extract_store_name(self, entries: list[dict]) -> Optional[str]:
        """
        Extract store name — typically one of the first clean short lines.
        Skips URLs, feedback prompts, IDs, addresses, and phone numbers.
        """
        lines = self._merge_into_lines(entries)
        for line_text in lines[:10]:
            text = line_text.strip()
            if len(text) < 2 or len(text) > 60:
                continue
            if self.PRICE_PATTERN.search(text):
                continue
            if any(p.search(text) for p in self.DATE_PATTERNS):
                continue
            if any(p.search(text) for p in self.SKIP_PATTERNS):
                continue
            if text.replace(" ", "").isdigit():
                continue
            # Skip lines that look like addresses (contain digits + street keywords)
            if re.search(r'\d+\s+\w+\s+(st|ave|blvd|rd|dr|ln|way|market)\b', text, re.IGNORECASE):
                continue
            # Skip lines with too many digits (barcodes, IDs)
            digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
            if digit_ratio > 0.5:
                continue
            return text
        return None

    def _extract_date(self, raw_text: str) -> Optional[str]:
        """Extract date from the receipt text."""
        for pattern in self.DATE_PATTERNS:
            match = pattern.search(raw_text)
            if match:
                date_str = match.group(1)
                parsed = self._parse_date_string(date_str)
                if parsed:
                    return parsed
        return None

    @staticmethod
    def _parse_date_string(date_str: str) -> Optional[str]:
        """Try to parse a date string into ISO format."""
        formats = [
            "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%Y/%m/%d",
            "%m/%d/%y", "%m-%d-%y", "%d/%m/%Y", "%d-%m-%Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _extract_items(self, entries: list[dict]) -> list[dict]:
        """
        Extract item names and prices.
        Groups OCR fragments into visual lines first, then parses each line.
        """
        items = []
        lines = self._merge_into_lines(entries)

        for text in lines:
            text = text.strip()

            if any(p.search(text) for p in self.SKIP_PATTERNS):
                continue
            if any(kw in text.lower() for kw in self.TOTAL_KEYWORDS):
                continue

            price_match = self.PRICE_PATTERN.search(text)
            if not price_match:
                continue

            price = float(price_match.group(1).replace(",", ""))
            if price <= 0 or price >= 10000:
                continue

            # Item name = everything before the price
            name = text[:price_match.start()].strip()

            # Strip barcode/product codes (long digit sequences)
            name = self.BARCODE_PATTERN.sub("", name).strip()
            # Strip trailing single letters (tax flags like "F", "X", "N")
            name = re.sub(r'\s+[A-Z]\s*$', '', name).strip()
            # Strip leading symbols/numbers
            name = re.sub(r'^[\d\s#*\-/]+', '', name).strip()
            # Normalize whitespace
            name = re.sub(r'\s+', ' ', name)

            if not name or len(name) < 2:
                continue

            # Detect quantity prefix: "2x Item" or "2 Item"
            qty_match = re.match(r'^(\d+)\s*[xX]\s+(.+)$', name)
            if qty_match:
                quantity = int(qty_match.group(1))
                name = qty_match.group(2).strip()
            else:
                quantity = 1

            items.append({"name": name, "price": round(price, 2), "quantity": quantity})

        logger.info(f"Extracted {len(items)} items from receipt")
        return items

    def _extract_total(self, entries: list[dict]) -> Optional[float]:
        """
        Extract the total amount. Prefers lines with 'total' keyword,
        skips subtotal/tax, falls back to largest price.
        """
        lines = self._merge_into_lines(entries)

        # First pass: look for "total" but not "subtotal"
        for text in lines:
            lower = text.lower()
            if "total" in lower and "subtotal" not in lower and "sub total" not in lower:
                price_match = self.PRICE_PATTERN.search(text)
                if price_match:
                    total = float(price_match.group(1).replace(",", ""))
                    if total > 0:
                        return round(total, 2)

        # Second pass: any total keyword
        for text in lines:
            lower = text.lower()
            if any(kw in lower for kw in self.TOTAL_KEYWORDS):
                price_match = self.PRICE_PATTERN.search(text)
                if price_match:
                    total = float(price_match.group(1).replace(",", ""))
                    if total > 0:
                        return round(total, 2)

        # Fallback: largest price
        prices = [float(m.group(1).replace(",", ""))
                  for t in lines for m in self.PRICE_PATTERN.finditer(t)]
        return round(max(prices), 2) if prices else None

    def _merge_into_lines(self, entries: list[dict], y_threshold: int = 12) -> list[str]:
        """
        Group OCR entries by Y-coordinate proximity into visual lines,
        then merge each line's text left-to-right.
        """
        if not entries:
            return []

        sorted_entries = sorted(entries, key=lambda e: e.get("center_y", 0))
        lines: list[list[dict]] = []
        current: list[dict] = [sorted_entries[0]]

        for entry in sorted_entries[1:]:
            if abs(entry.get("center_y", 0) - current[-1].get("center_y", 0)) <= y_threshold:
                current.append(entry)
            else:
                lines.append(current)
                current = [entry]
        lines.append(current)

        merged = []
        for line in lines:
            line.sort(key=lambda e: e.get("center_x", 0))
            merged.append("  ".join(e["text"] for e in line))
        return merged
