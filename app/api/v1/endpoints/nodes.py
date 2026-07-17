from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.sql.document import DocumentVersion
from app.models.sql.node import Node
from app.schemas.node import NodeChangeRead, NodeRead, PaginatedNodes

# Routers to bind on specific prefixes
nodes_router = APIRouter()
search_router = APIRouter()
changes_router = APIRouter()


@nodes_router.get("/{id}", response_model=NodeRead)
async def get_node(
    id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> NodeRead:
    """Fetch a specific node by its unique physical UUID."""
    stmt = select(Node).where(Node.id == id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with ID {id} not found.",
        )

    return node


@search_router.get("", response_model=PaginatedNodes)
async def search_nodes(
    q: str = Query(..., min_length=1, description="Search query string"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(deps.get_db),
) -> PaginatedNodes:
    """Search for nodes containing the query text inside their content (case-insensitive)."""
    offset = (page - 1) * size
    search_filter = f"%{q}%"

    # Count matching nodes
    count_stmt = select(func.count(Node.id)).where(
        Node.content.ilike(search_filter)
    )
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Get matching nodes
    select_stmt = (
        select(Node)
        .where(Node.content.ilike(search_filter))
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(select_stmt)
    items = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

    return PaginatedNodes(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@changes_router.get("/{node_id}", response_model=List[NodeChangeRead])
async def get_node_changes(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> List[NodeChangeRead]:
    """Fetch the change history of a logical node across multiple document versions.

    Ordered chronologically by version number.
    """
    stmt = (
        select(
            Node.id,
            Node.logical_id,
            Node.version_id,
            DocumentVersion.version_number,
            Node.node_type,
            Node.content,
            Node.content_hash,
            Node.position,
            Node.created_at,
        )
        .join(DocumentVersion, Node.version_id == DocumentVersion.id)
        .where(Node.logical_id == node_id)
        .order_by(DocumentVersion.version_number.asc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Logical node {node_id} has no version history.",
        )

    # Convert query result row tuples into Pydantic models (supported via mapping)
    changes = [
        NodeChangeRead(
            id=row.id,
            logical_id=row.logical_id,
            version_id=row.version_id,
            version_number=row.version_number,
            node_type=row.node_type,
            content=row.content,
            content_hash=row.content_hash,
            position=row.position,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return changes
