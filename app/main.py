"""
SplitsenseAI — FastAPI Application Entry Point
AI Expense Intelligence & Smart Bill Splitting System
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import logger
from app.api.v1.router import api_router

settings = get_settings()


def _preload_models():
    """Load heavy ML models once at startup so first request is fast."""
    try:
        from ml.categorizer.zero_shot import ZeroShotCategorizer
        ZeroShotCategorizer()
        logger.info("Zero-shot categorizer loaded")
    except Exception as e:
        logger.warning(f"Zero-shot categorizer preload failed (non-fatal): {e}")

    try:
        from ml.categorizer.classifier import TrainedClassifier
        TrainedClassifier()
        logger.info("Trained classifier checked")
    except Exception as e:
        logger.warning(f"Trained classifier preload failed (non-fatal): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    import asyncio
    logger.info(f"🚀 Starting {settings.APP_NAME} ({settings.APP_ENV})")
    logger.info(f"📡 API docs at http://localhost:8000/docs")
    logger.info("Preloading ML models in background thread...")
    asyncio.get_event_loop().run_in_executor(None, _preload_models)
    yield
    logger.info(f"👋 Shutting down {settings.APP_NAME}")


app = FastAPI(
    title="SplitsenseAI",
    description="AI Expense Intelligence & Smart Bill Splitting System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS (controlled via CORS_ORIGINS env var) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include API routes ---
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
