"""
Automated API test script — runs through the full flow and reports results.
Usage: python test_api.py
"""

import requests
import json
import io
import sys
from PIL import Image, ImageDraw

BASE = "http://localhost:8000/api/v1"
PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"
INFO = "\033[94m INFO\033[0m"

results = []


def check(name, response, expected_status):
    ok = response.status_code == expected_status
    symbol = PASS if ok else FAIL
    print(f"{symbol}  {name} [{response.status_code}]")
    if not ok:
        try:
            print(f"       {json.dumps(response.json(), indent=2)}")
        except Exception:
            print(f"       {response.text[:300]}")
    results.append((name, ok))
    return response


def make_receipt_image() -> bytes:
    img = Image.new("RGB", (400, 600), color="white")
    draw = ImageDraw.Draw(img)
    lines = [
        "WALMART SUPERCENTER",
        "123 Main St, Dallas TX",
        "----------------------------",
        "Milk 2%            $3.49",
        "Bread Wheat        $2.99",
        "Eggs Large 12pk    $4.79",
        "Orange Juice 1L    $3.29",
        "Chicken Breast     $8.99",
        "----------------------------",
        "SUBTOTAL          $23.55",
        "TAX (8%)           $1.88",
        "TOTAL             $25.43",
    ]
    y = 40
    for line in lines:
        draw.text((30, y), line, fill="black")
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ── 1. Auth ──────────────────────────────────────────────────────────────────
print("\n── Authentication ──────────────────────────────────────────────────")

r = requests.post(f"{BASE}/auth/register", json={
    "email": "testuser@splitsense.com",
    "username": "testuser",
    "password": "Test@1234",
})
if r.status_code == 201:
    check("Register user", r, 201)
elif r.status_code == 400 and "already registered" in r.text:
    print(f"{INFO}  User exists — logging in")
    r = check("Login", requests.post(f"{BASE}/auth/login", json={
        "email": "testuser@splitsense.com",
        "password": "Test@1234",
    }), 200)
else:
    check("Register user", r, 201)

token = r.json().get("access_token", "")
if not token:
    print(f"\n{FAIL}  Could not get token — is uvicorn running?")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

me = check("GET /auth/me", requests.get(f"{BASE}/auth/me", headers=headers), 200)
user_id = me.json().get("id") if me.ok else None

check("GET /auth/users/search?q=test", requests.get(f"{BASE}/auth/users/search?q=test", headers=headers), 200)

# ── 2. Groups ─────────────────────────────────────────────────────────────────
print("\n── Groups ──────────────────────────────────────────────────────────")

r = check("POST /groups/", requests.post(f"{BASE}/groups/", headers=headers, json={
    "name": "Test Trip",
    "description": "Automated test group",
}), 201)
group_id = r.json().get("id") if r.ok else None

check("GET /groups/", requests.get(f"{BASE}/groups/", headers=headers), 200)
if group_id:
    check(f"GET /groups/{{id}}", requests.get(f"{BASE}/groups/{group_id}", headers=headers), 200)

# ── 3. Receipts ───────────────────────────────────────────────────────────────
print("\n── Receipts ────────────────────────────────────────────────────────")

receipt_id = None
try:
    image_bytes = make_receipt_image()
    params = {"group_id": group_id} if group_id else {}
    r = check("POST /receipts/upload", requests.post(
        f"{BASE}/receipts/upload",
        headers=headers,
        files={"file": ("receipt.jpg", image_bytes, "image/jpeg")},
        params=params,
    ), 201)
    receipt_id = r.json().get("id") if r.ok else None
except Exception as e:
    print(f"{FAIL}  POST /receipts/upload — exception: {e}")
    results.append(("POST /receipts/upload", False))

check("GET /receipts/", requests.get(f"{BASE}/receipts/", headers=headers), 200)
if receipt_id:
    check(f"GET /receipts/{{id}}", requests.get(f"{BASE}/receipts/{receipt_id}", headers=headers), 200)

# ── 4. Splits ─────────────────────────────────────────────────────────────────
print("\n── Splits ──────────────────────────────────────────────────────────")

if receipt_id and user_id:
    # Get the actual item IDs from the uploaded receipt
    receipt_data = requests.get(f"{BASE}/receipts/{receipt_id}", headers=headers).json()
    items = receipt_data.get("items", [])
    if items:
        assignments = [
            {"item_id": item["id"], "user_id": user_id, "split_type": "equal", "share_value": 1.0}
            for item in items
        ]
        r = check("POST /splits/receipt/{id}", requests.post(
            f"{BASE}/splits/receipt/{receipt_id}",
            headers=headers,
            json={"receipt_id": receipt_id, "assignments": assignments},
        ), 200)
    else:
        print(f"{INFO}  Skipping split POST — receipt has no items (OCR found nothing)")
    check("GET /splits/receipt/{id}", requests.get(f"{BASE}/splits/receipt/{receipt_id}", headers=headers), 200)
else:
    print(f"{INFO}  Skipping splits — no receipt_id (upload failed)")

# ── 5. Settlements ────────────────────────────────────────────────────────────
print("\n── Settlements ─────────────────────────────────────────────────────")

if group_id:
    check("GET /settlements/group/{id}/balances",
          requests.get(f"{BASE}/settlements/group/{group_id}/balances", headers=headers), 200)
    check("GET /settlements/group/{id}/history",
          requests.get(f"{BASE}/settlements/group/{group_id}/history", headers=headers), 200)

# ── 6. Analytics ──────────────────────────────────────────────────────────────
print("\n── Analytics ───────────────────────────────────────────────────────")

check("GET /analytics/spending",  requests.get(f"{BASE}/analytics/spending",  headers=headers), 200)
check("GET /analytics/trends",    requests.get(f"{BASE}/analytics/trends",    headers=headers), 200)
check("GET /analytics/insights",  requests.get(f"{BASE}/analytics/insights",  headers=headers), 200)

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"\n── Results: {passed}/{total} passed {'✓' if passed == total else '✗'} ──────────────────────────────────")
if passed < total:
    print("Failed:")
    for name, ok in results:
        if not ok:
            print(f"   • {name}")
