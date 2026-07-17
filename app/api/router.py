from fastapi import APIRouter

from app.api.v1.router import api_router as v1_router
from app.core.config import settings

api_router = APIRouter()

# Include version 1 API routes
api_router.include_router(v1_router, prefix=settings.API_V1_STR)
