import hashlib
import json
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.document import Document, DocumentVersion
from app.models.sql.llm_failure import LLMFailureLog
from app.models.sql.node import Node
from app.models.sql.selection import Selection, SelectionNodeMapping
from app.services.pdf.llm_service import LLMIntegrationService


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def llm_service() -> LLMIntegrationService:
    return LLMIntegrationService()


def test_reconstruct_text_with_offsets(llm_service: LLMIntegrationService) -> None:
    """Verifies that reconstruct_text joins node contents correctly, respecting offsets."""
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    sel_id = uuid.uuid4()

    # Create mock Selection and associated mapped nodes
    selection = Selection(
        id=sel_id,
        document_id=doc_id,
        version_id=ver_id,
    )

    node1 = Node(
        id=uuid.uuid4(),
        node_type="paragraph",
        content="Hello world, this is a test.",
        position=0,
        content_hash="hash1",
        version_id=ver_id,
    )
    node2 = Node(
        id=uuid.uuid4(),
        node_type="paragraph",
        content="Second node text.",
        position=1,
        content_hash="hash2",
        version_id=ver_id,
    )

    mapping1 = SelectionNodeMapping(
        selection_id=sel_id,
        node_id=node1.id,
        anchor_offset=6,
        focus_offset=11,  # Should slice "world"
        node=node1,
    )
    mapping2 = SelectionNodeMapping(
        selection_id=sel_id,
        node_id=node2.id,
        anchor_offset=None,
        focus_offset=None,  # No slice
        node=node2,
    )

    selection.node_mappings = [mapping1, mapping2]

    reconstructed = llm_service.reconstruct_text(selection)
    assert reconstructed == "world\nSecond node text."


@pytest.mark.asyncio
async def test_llm_qa_generation_success(
    client: AsyncClient, db_session: AsyncSession, llm_service: LLMIntegrationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests successful QA generation route when the API returns valid JSON."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Manual guide")
    db_session.add(doc)

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="V1",
    )
    db_session.add(version)
    await db_session.commit()

    node_id = uuid.uuid4()
    node = Node(
        id=node_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="Testing content.",
        content_hash="hash",
        position=0,
    )
    db_session.add(node)
    await db_session.commit()

    sel_id = uuid.uuid4()
    selection = Selection(
        id=sel_id,
        document_id=doc_id,
        version_id=ver_id,
    )
    db_session.add(selection)
    await db_session.flush()

    mapping = SelectionNodeMapping(selection_id=sel_id, node_id=node_id)
    db_session.add(mapping)
    await db_session.commit()

    # Mock LLM API call response
    expected_response = {
        "test_cases": [
            {"question": "What are we testing?", "answer": "Testing content."}
        ]
    }

    async def mock_call_gemini_api(self, prompt: str) -> str:
        return json.dumps(expected_response)

    monkeypatch.setattr(LLMIntegrationService, "_call_gemini_api", mock_call_gemini_api)

    response = await client.post(f"/api/v1/selection/{sel_id}/generate-qa")
    assert response.status_code == 200
    data = response.json()

    assert "test_cases" in data
    assert len(data["test_cases"]) == 1
    assert data["test_cases"][0]["question"] == "What are we testing?"
    assert data["test_cases"][0]["answer"] == "Testing content."


@pytest.mark.asyncio
async def test_llm_qa_generation_retry_recovery(
    client: AsyncClient, db_session: AsyncSession, llm_service: LLMIntegrationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests that the service retries once and recovers if the first LLM payload is invalid but the second is valid."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Manual guide 2")
    db_session.add(doc)

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="V1",
    )
    db_session.add(version)
    await db_session.commit()

    node_id = uuid.uuid4()
    node = Node(
        id=node_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="Testing content 2.",
        content_hash="hash2",
        position=0,
    )
    db_session.add(node)
    await db_session.commit()

    sel_id = uuid.uuid4()
    selection = Selection(id=sel_id, document_id=doc_id, version_id=ver_id)
    db_session.add(selection)
    await db_session.flush()

    mapping = SelectionNodeMapping(selection_id=sel_id, node_id=node_id)
    db_session.add(mapping)
    await db_session.commit()

    # Track attempts
    calls = []

    async def mock_call_gemini_api_retry(self, prompt: str) -> str:
        calls.append(1)
        if len(calls) == 1:
            # First attempt: invalid format
            return "This is not valid JSON string at all!"
        # Second attempt: valid format
        return json.dumps({
            "test_cases": [
                {"question": "Retry question?", "answer": "Retry answer."}
            ]
        })

    monkeypatch.setattr(LLMIntegrationService, "_call_gemini_api", mock_call_gemini_api_retry)

    response = await client.post(f"/api/v1/selection/{sel_id}/generate-qa")
    assert response.status_code == 200
    data = response.json()

    assert len(calls) == 2  # Proves it retried exactly once!
    assert data["test_cases"][0]["question"] == "Retry question?"


@pytest.mark.asyncio
async def test_llm_qa_generation_failure_logged(
    client: AsyncClient, db_session: AsyncSession, llm_service: LLMIntegrationService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests that a double LLM validation failure triggers database error logging and returns HTTP 500."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Manual guide 3")
    db_session.add(doc)

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="V1",
    )
    db_session.add(version)
    await db_session.commit()

    node_id = uuid.uuid4()
    node = Node(
        id=node_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="Testing content 3.",
        content_hash="hash3",
        position=0,
    )
    db_session.add(node)
    await db_session.commit()

    sel_id = uuid.uuid4()
    selection = Selection(id=sel_id, document_id=doc_id, version_id=ver_id)
    db_session.add(selection)
    await db_session.flush()

    mapping = SelectionNodeMapping(selection_id=sel_id, node_id=node_id)
    db_session.add(mapping)
    await db_session.commit()

    # Both attempts return invalid JSON
    async def mock_call_gemini_api_fail(self, prompt: str) -> str:
        return "{'broken_json': true}"  # Broken single quotes

    monkeypatch.setattr(LLMIntegrationService, "_call_gemini_api", mock_call_gemini_api_fail)

    response = await client.post(f"/api/v1/selection/{sel_id}/generate-qa")
    assert response.status_code == 500
    assert "Failed to generate valid QA test cases after 2 attempts" in response.json()["detail"]

    # Verify database failure log was written
    # We open a new query on the database to check LLMFailureLog records
    stmt = select(LLMFailureLog).where(LLMFailureLog.selection_id == sel_id)
    res = await db_session.execute(stmt)
    failure = res.scalar_one_or_none()

    assert failure is not None
    assert "broken_json" in failure.raw_response
    assert "Validation failed after 2 attempts" in failure.error_message
