import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.sql.document import DocumentVersion
from app.models.sql.node import Node
from app.models.sql.selection import Selection, SelectionNodeMapping
from app.schemas.selection import QATestCaseList, SelectionCreate, SelectionRead
from app.services.pdf.llm_service import LLMIntegrationService

router = APIRouter()
llm_service = LLMIntegrationService()


@router.post("", response_model=SelectionRead, status_code=status.HTTP_201_CREATED)
async def create_selection(
    payload: SelectionCreate,
    db: AsyncSession = Depends(deps.get_db),
) -> SelectionRead:
    """Creates a new user selection pinned to a specific document version.

    Validates that the version exists and all node IDs belong to that version.
    """
    # 1. Validate Document Version existence
    ver_stmt = select(DocumentVersion).where(
        DocumentVersion.id == payload.version_id
    )
    ver_res = await db.execute(ver_stmt)
    version = ver_res.scalar_one_or_none()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document version {payload.version_id} not found.",
        )

    # 2. Validate all Node IDs exist and belong to the specified version
    if not payload.node_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selections must associate with at least one node ID.",
        )

    nodes_stmt = select(Node.id).where(
        Node.id.in_(payload.node_ids), Node.version_id == payload.version_id
    )
    nodes_res = await db.execute(nodes_stmt)
    valid_node_ids = set(nodes_res.scalars().all())

    missing_node_ids = set(payload.node_ids) - valid_node_ids
    if missing_node_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The following node IDs are invalid or do not belong to "
                f"version {payload.version_id}: {list(missing_node_ids)}"
            ),
        )

    # 3. Create the selection record
    selection = Selection(
        id=uuid.uuid4(),
        document_id=version.document_id,
        version_id=payload.version_id,
        name=payload.name,
    )
    db.add(selection)
    await db.flush()  # Flush to register ID for parent reference

    # 4. Bind the node mapping relationships
    for nid in payload.node_ids:
        mapping = SelectionNodeMapping(
            selection_id=selection.id,
            node_id=nid,
        )
        db.add(mapping)

    await db.commit()
    await db.refresh(selection)

    # 5. Build and return schema response
    return SelectionRead(
        id=selection.id,
        document_id=selection.document_id,
        version_id=selection.version_id,
        name=selection.name,
        node_ids=[m.node_id for m in selection.node_mappings],
        created_at=selection.created_at,
    )


@router.get("/{id}", response_model=SelectionRead)
async def get_selection(
    id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> SelectionRead:
    """Fetch a specific user selection and its mapped node IDs."""
    stmt = select(Selection).where(Selection.id == id)
    result = await db.execute(stmt)
    selection = result.scalar_one_or_none()

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection with ID {id} not found.",
        )

    return SelectionRead(
        id=selection.id,
        document_id=selection.document_id,
        version_id=selection.version_id,
        name=selection.name,
        node_ids=[m.node_id for m in selection.node_mappings],
        created_at=selection.created_at,
    )


@router.post("/{id}/generate-qa", response_model=QATestCaseList)
async def generate_qa_from_selection(
    id: uuid.UUID,
    db: AsyncSession = Depends(deps.get_db),
) -> QATestCaseList:
    """Reconstructs selected text and generates 3-5 QA test cases using an LLM.

    Saves validation failures to the audit database log and raises HTTP 500 if generation fails twice.
    """
    # 1. Fetch selection
    stmt = select(Selection).where(Selection.id == id)
    result = await db.execute(stmt)
    selection = result.scalar_one_or_none()

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection with ID {id} not found.",
        )

    # 2. Run LLM generation
    try:
        qa_list = await llm_service.generate_qa_test_cases(selection, db)
        return qa_list
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
