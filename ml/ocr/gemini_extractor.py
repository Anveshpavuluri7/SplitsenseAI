"""
Vision receipt extractor using Groq's Llama 3.2 Vision API.
Free tier: 30 RPM, 1400 req/day — no credit card required.
Keeps the same extract_receipt() interface so receipts.py is unchanged.
"""

import io
import json
import base64
import logging
import re
import time
import requests
from typing import Optional

logger = logging.getLogger("splitsenseai.ocr.groq")

PROMPT = """You are a receipt parser. Analyze this receipt image and extract the data.

Return ONLY a valid JSON object — no markdown, no explanation, just JSON:
{
  "store_name": "store name or null",
  "receipt_date": "YYYY-MM-DD or null",
  "items": [
    {"name": "item name", "price": 0.00, "quantity": 1}
  ],
  "total": 0.00
}

Rules:
- items: only actual purchased products, not tax/subtotal/payment lines
- price: the unit price as a float
- quantity: integer (default 1)
- total: the final TOTAL amount paid (not subtotal)
- If a field cannot be determined, use null
"""

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.2-11b-vision-preview",
    "llama-3.2-90b-vision-preview",
]


def _prepare_image(image_bytes: bytes) -> tuple[bytes, str]:
    """Resize to max 1280px long side and normalise orientation."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)

    w, h = img.size
    max_dim = 1280
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    if img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), "image/jpeg"


def extract_receipt(image_bytes: bytes) -> dict:
    """
    Send receipt image to Groq Llama Vision and parse the response.

    Returns:
        {
            "store_name": str | None,
            "receipt_date": str | None,   # YYYY-MM-DD
            "items": [{"name", "price", "quantity"}, ...],
            "total": float | None,
            "raw_text": str,
        }
    """
    from app.core.config import get_settings

    settings = get_settings()
    api_key = settings.GROQ_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set in .env")

    resized_bytes, mime = _prepare_image(image_bytes)
    b64 = base64.b64encode(resized_bytes).decode()
    logger.info(f"Image prepared: {len(resized_bytes) // 1024}KB JPEG")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = None
    used_model = None
    for model in _MODELS:
        logger.info(f"Trying Groq model: {model}")
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }],
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        try:
            r = requests.post(_GROQ_URL, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                resp = r
                used_model = model
                break
            if r.status_code == 429:
                logger.warning(f"  → 429 rate limit, waiting 12s...")
                time.sleep(12)
                r = requests.post(_GROQ_URL, headers=headers, json=payload, timeout=60)
                if r.status_code == 200:
                    resp = r
                    used_model = model
                    break
            logger.warning(f"  → {r.status_code}: {r.text[:200]}")
        except requests.RequestException as exc:
            logger.warning(f"  → request error: {exc}")

    if resp is None:
        raise RuntimeError("All Groq models failed — check GROQ_API_KEY and network")

    logger.info(f"Response from {used_model}")

    try:
        raw_text = resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Groq response: {resp.text[:300]}") from exc

    logger.info(f"Raw response: {raw_text[:200]}")

    # Strip markdown fences if the model added them
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            logger.error(f"Could not parse JSON from response: {cleaned}")
            data = {}

    items = []
    for item in data.get("items") or []:
        name = str(item.get("name", "")).strip()
        price = _to_float(item.get("price"))
        qty = int(item.get("quantity") or 1)
        if name and price is not None and price > 0:
            items.append({"name": name, "price": round(price, 2), "quantity": qty})

    result = {
        "store_name": data.get("store_name") or None,
        "receipt_date": _clean_date(data.get("receipt_date")),
        "items": items,
        "total": _to_float(data.get("total")),
        "raw_text": raw_text,
    }

    logger.info(
        f"Extracted: store={result['store_name']}, "
        f"items={len(items)}, total={result['total']}"
    )
    return result


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(str(value).replace(",", "").replace("$", "")), 2)
    except (ValueError, TypeError):
        return None


def _clean_date(value) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return None
