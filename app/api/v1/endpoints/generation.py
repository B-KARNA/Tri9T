import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.sql.node import Node
from app.models.sql.selection import Selection, SelectionNodeMapping
from app.schemas.selection import GenerationRetrievalResponse
from app.services.pdf.llm_service import LLMIntegrationService

router = APIRouter()
llm_service = LLMIntegrationService()


@router.get("/{selection_id}", response_model=GenerationRetrievalResponse)
async def get_generation_by_selection(
    selection_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> GenerationRetrievalResponse:
    """Retrieves the QA generation report and staleness diff for a specific selection ID."""
    try:
        report = await llm_service.get_generation_report(selection_id, db)
        return GenerationRetrievalResponse(**report)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/node/{node_id}", response_model=List[GenerationRetrievalResponse])
async def get_generation_by_node(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> List[GenerationRetrievalResponse]:
    """Retrieves the QA generation report and staleness diff for all selections containing the specified node ID."""
        # 1. Fetch the node to get its logical ID
    node_stmt = select(Node).where(
        (Node.id == node_id) | (Node.logical_id == node_id)
    )
    node_res = await db.execute(node_stmt)
    node = node_res.scalars().first()

    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with ID {node_id} not found.",
        )

    # 2. Query all distinct Selection IDs mapped to this logical node ID
    sel_stmt = (
        select(Selection.id)
        .join(
            SelectionNodeMapping, Selection.id == SelectionNodeMapping.selection_id
        )
        .join(Node, SelectionNodeMapping.node_id == Node.id)
        .where(Node.logical_id == node.logical_id)
        .distinct()
    )
    sel_res = await db.execute(sel_stmt)
    selection_ids = sel_res.scalars().all()

    # 3. Generate reports for each matching selection
    reports = []
    for sel_id in selection_ids:
        try:
            report = await llm_service.get_generation_report(sel_id, db)
            reports.append(GenerationRetrievalResponse(**report))
        except ValueError:
            # Skip if generation report fails (e.g. selection deleted)
            continue

    return reports
