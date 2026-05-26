"""API v1 router — aggregates all endpoint routers."""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.receipts import router as receipts_router
from app.api.v1.endpoints.groups import router as groups_router
from app.api.v1.endpoints.splits import router as splits_router
from app.api.v1.endpoints.settlements import router as settlements_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.exports import router as exports_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(receipts_router)
api_router.include_router(groups_router)
api_router.include_router(splits_router)
api_router.include_router(settlements_router)
api_router.include_router(analytics_router)
api_router.include_router(exports_router)
