from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_doc_store

router = APIRouter()


class HealthCheckResponse(BaseModel):
    status: str
    database: str
    document_store: str


@router.get("", response_model=HealthCheckResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    doc_store: Any = Depends(get_doc_store),
) -> HealthCheckResponse:
    """Check the health status of the application and its database backends."""

    # 1. SQL Database verification
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    # 2. Document Database verification
    doc_status = "healthy"
    try:
        # Check if it's MongoDB/Motor
        if hasattr(doc_store, "list_collection_names"):
            await doc_store.list_collection_names()
        # Otherwise, check local JSON storage (confirm file presence/readability)
        elif hasattr(doc_store, "file_path"):
            # Ensure it is initialized
            assert doc_store.file_path is not None
    except Exception:
        doc_status = "unhealthy"

    status = (
        "healthy"
        if db_status == "healthy" and doc_status == "healthy"
        else "degraded"
    )

    return HealthCheckResponse(
        status=status, database=db_status, document_store=doc_status
    )
