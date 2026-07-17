from typing import Optional
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.sql.document import Document, DocumentVersion
from app.schemas.document import (
    DocumentRead,
    DocumentVersionRead,
    PaginatedDocuments,
    PaginatedDocumentVersions,
)

# We define separate routers to bind cleanly on different prefixes at v1 router inclusion.
documents_router = APIRouter()
versions_router = APIRouter()


@documents_router.get("", response_model=PaginatedDocuments)
async def get_documents(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(deps.get_db),
) -> PaginatedDocuments:
    """Fetch a paginated list of documents."""
    offset = (page - 1) * size

    # Get total count
    total_query = select(func.count(Document.id))
    total_result = await db.execute(total_query)
    total = total_result.scalar_one()

    # Get paginated documents
    stmt = (
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedDocuments(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@versions_router.get("", response_model=PaginatedDocumentVersions)
async def get_versions(
    document_id: Optional[uuid.UUID] = Query(
        None, description="Filter versions by Document ID"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(deps.get_db),
) -> PaginatedDocumentVersions:
    """Fetch a paginated list of document versions, optionally filtered by Document ID."""
    offset = (page - 1) * size

    # Build base queries
    count_stmt = select(func.count(DocumentVersion.id))
    select_stmt = select(DocumentVersion).order_by(
        DocumentVersion.version_number.desc()
    )

    if document_id is not None:
        count_stmt = count_stmt.where(
            DocumentVersion.document_id == document_id
        )
        select_stmt = select_stmt.where(
            DocumentVersion.document_id == document_id
        )

    # Exec count
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Exec select
    select_stmt = select_stmt.offset(offset).limit(size)
    result = await db.execute(select_stmt)
    items = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedDocumentVersions(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
