# SplitsenseAI

**AI Expense Intelligence & Smart Bill Splitting System**

A production-grade full-stack application that uses Groq Llama Vision for receipt OCR, ML-powered expense categorization, and smart multi-user bill splitting with real-time analytics.

---

## Architecture

```
┌──────────────────┐     ┌─────────────────────────────────────────────┐
│  Streamlit       │     │              FastAPI Backend                │
│  Dashboard       │───▶ │ ┌──────┐  ┌──────────┐  ┌─────────────┐     │
│  (Port 8501)     │     │  │ Auth │  │ Receipts │  │ Settlements │    │
└──────────────────┘     │  │ JWT  │  │ + Items  │  │   Engine    │    │
                         │  └──────┘  └────┬─────┘  └─────────────┘    │
                         │                 │                           │
                         │  ┌──────────────▼──────────────────────┐    │
                         │  │            ML Services              │    │
                         │  │  Groq Vision OCR  │  Categorizer    │    │
                         │  │  (Llama 4 Scout)  │  (BART-MNLI)    │    │
                         │  └─────────────────────────────────────┘    │
                         │                 │                           │
                         │  ┌──────────────▼──────┐  ┌─────────────┐   │
                         │  │  PostgreSQL (async) │  │  Cloudinary │   │
                         │  │  8 tables           │  │  (Images)   │   │
                         │  └─────────────────────┘  └─────────────┘   │
                         └─────────────────────────────────────────────┘
```

## Features

- **Receipt OCR** — Groq Llama 4 Scout 17B Vision API extracts store, date, items and total from a photo in ~1.5s
- **Background Processing** — Upload returns instantly; OCR + categorization run in a background task
- **ML Categorization** — Zero-shot (BART-MNLI) + sentence-transformers trained classifier assigns categories automatically
- **Item Correction** — Edit any extracted item's name, price, quantity, or category; receipt total recalculates automatically
- **Bill Splitting** — Assign items to group members; equal, percentage, or personal split modes
- **Settlement Engine** — Min-transactions algorithm computes the optimal payment plan to settle all debts
- **Cloud Image Storage** — Receipt photos uploaded to Cloudinary; thumbnail shown inside each receipt card
- **Analytics Dashboard** — Category/store spending, monthly trends, and insight cards powered by Plotly
- **Receipt Management** — Status tabs (All / Ready / Error / Processing), bulk-delete error receipts, delete individual receipts
- **Excel Export** — Styled reports with transactions and settlements sheets
- **JWT Auth** — Register/login with bcrypt-hashed passwords and 24h tokens

## Tech Stack

| Layer             | Technology                                                  |
|-------------------|-------------------------------------------------------------|
| **Backend**       | FastAPI, SQLAlchemy (async), Alembic                        |
| **Database**      | PostgreSQL + asyncpg                                        |
| **Vision OCR**    | Groq API - Llama 4 Scout 17B / Llama 3.2 Vision (free tier) |
| **ML**            | sentence-transformers, HuggingFace BART-MNLI, spaCy         |
| **Frontend**      | Streamlit, Plotly                                           |
| **Image Storage** | Cloudinary (free tier - 25 GB)                              |
| **Auth**          | JWT via python-jose + passlib/bcrypt                        |
| **Export**        | openpyxl                                                    |
| **Deployment**    | Render (backend + PostgreSQL), Streamlit Cloud (frontend)   |

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL running locally
- Free API keys: [Groq](https://console.groq.com) · [Cloudinary](https://cloudinary.com)

### 1. Clone & configure

```bash
git clone https://github.com/Anveshpavuluri7/SplitsenseAI.git
cd SplitsenseAI
cp .env.example .env
# Fill in DATABASE_URL, GROQ_API_KEY, CLOUDINARY_* in .env
```

### 2. Install dependencies & migrate

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
python -m spacy download en_core_web_sm

alembic upgrade head
```

### 3. Run the backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# API docs → http://localhost:8000/docs
```

### 4. Run the dashboard

```bash
streamlit run dashboard.py
# Dashboard → http://localhost:8501
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/splitsenseai

# Auth
SECRET_KEY=your-32-byte-hex-secret
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Groq Vision OCR (free — https://console.groq.com)
GROQ_API_KEY=gsk_...

# Cloudinary image storage (free — https://cloudinary.com)
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# App
APP_ENV=development
API_BASE_URL=http://localhost:8000
```

## Project Structure

```
SplitsenseAI/
├── app/
│   ├── api/v1/endpoints/     # auth, receipts, groups, splits, settlements, analytics, exports
│   ├── core/                 # config (pydantic-settings), logging
│   ├── db/                   # async engine & session factory
│   ├── models/               # SQLAlchemy ORM — users, receipts, items, groups, transactions, settlements
│   ├── schemas/              # Pydantic v2 request/response models
│   ├── services/             # business logic — receipt, split, settlement, analytics, export
│   └── main.py               # FastAPI app + lifespan (ML model preload)
├── ml/
│   ├── ocr/
│   │   └── gemini_extractor.py   # Groq Vision API client (despite filename — uses Groq)
│   ├── categorizer/
│   │   ├── zero_shot.py          # BART-MNLI zero-shot classifier
│   │   ├── classifier.py         # sentence-transformers trained classifier
│   │   └── embedder.py           # all-MiniLM-L6-v2 embeddings
│   └── ner/                      # spaCy entity extractor
├── dashboard.py              # Streamlit single-page app
├── alembic/                  # DB migration scripts
├── render.yaml               # Render deployment blueprint
├── requirements.txt          # Backend + ML dependencies
├── requirements_frontend.txt # Streamlit Cloud (lightweight)
└── .env.example
```

## API Reference

| Method     | Endpoint                                   | Description                            |
|------------|--------------------------------------------|----------------------------------------|
| `POST`     | `/api/v1/auth/register`                    | Create account                         |
| `POST`     | `/api/v1/auth/login`                       | Login -> JWT token                     |
| `POST`     | `/api/v1/receipts/upload`                  | Upload image -> OCR in background      |
| `GET`      | `/api/v1/receipts/`                        | List receipts (paginated)              |
| `GET`      | `/api/v1/receipts/{id}`                    | Get receipt + items                    |
| `PATCH`    | `/api/v1/receipts/{id}/items/{item_id}`    | Correct item - name/price/qty/category |
| `DELETE`   | `/api/v1/receipts/{id}`                    | Delete receipt + items                 |
| `POST`     | `/api/v1/groups/`                          | Create group                           |
| `POST`     | `/api/v1/groups/{id}/members`              | Add member                             |
| `POST`     | `/api/v1/splits/receipt/{id}`              | Assign items to members                |
| `GET`      | `/api/v1/settlements/group/{id}/balances`  | Net balances + optimal payment plan    |
| `POST`     | `/api/v1/settlements/group/{id}/settle`    | Record a payment                       |
| `GET`      | `/api/v1/analytics/insights`               | Full spending insights                 |
| `GET`      | `/api/v1/exports/excel`                    | Download Excel report                  |

## ML Pipeline

```
Receipt image
     │
     ▼
Groq Llama Vision API  ──────────────────────────────────┐
(Llama 4 Scout 17B)                                       │
     │  JSON: {store, date, items[], total}               │
     ▼                                                    │
Item Categorizer                                          │
  ├── TrainedClassifier (sentence-transformers)           │
  │   └── falls back to ↓ if no trained model found      │
  └── ZeroShotCategorizer (BART-MNLI)                     │
       15 categories: Groceries, Restaurant, ...          │
                                                          │
Cloudinary Upload ◀───────────────────────────────────────┘
(receipt image → secure URL saved on receipt)
```

**Groq free tier**: 30 RPM, 1400 requests/day — no credit card required.

## Cloud Deployment

The repo ships a `render.yaml` blueprint for one-click deployment to Render + Streamlit Cloud.

### Backend → Render

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New Blueprint** → select your repo
3. Render reads `render.yaml` and creates: web service + free PostgreSQL
4. Set secret env vars in the Render dashboard: `GROQ_API_KEY`, `CLOUDINARY_*`

### Frontend → Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select repo
2. Set **Main file path**: `dashboard.py`
3. Under **Advanced > Environment variables**, add:

   ```env
   API_BASE_URL = https://your-app-name.onrender.com
   ```

4. Deploy

## How Settlements Work

1. One user uploads and pays the receipt
2. On the **Splits** page, assign each item to whoever consumed it
3. Members assigned items (other than the payer) become debtors
4. The **Settlement Engine** uses a min-transactions greedy algorithm to compute the smallest number of payments needed to clear all debts
5. On the **Settlements** page, select the group → **Balances** shows who owes whom
6. Click **Record Payment** once money changes hands to mark it settled

> Note: Items assigned back to the uploader (payer) do not create a debt — the payer already covered their own share.

## License

MIT License — see [LICENSE](LICENSE) for details.

---
⭐ Star this repo if you found it useful!

**Built with ❤️ by [Anvesh Pavuluri](https://github.com/Anveshpavuluri7)** 
