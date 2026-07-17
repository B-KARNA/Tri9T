import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.document import Document, DocumentVersion
from app.models.sql.node import Node


def make_hash(text: str) -> str:
    """Helper to generate a SHA-256 hash string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_get_documents_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /api/v1/documents returns paginated documents."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Test REST Doc")
    db_session.add(doc)
    await db_session.commit()

    response = await client.get("/api/v1/documents?page=1&size=10")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["size"] == 10
    assert any(item["name"] == "Test REST Doc" for item in data["items"])


@pytest.mark.asyncio
async def test_get_versions_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /api/v1/versions returns paginated versions."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Test Version Doc")
    db_session.add(doc)
    await db_session.commit()

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Doc V1 Content",
    )
    db_session.add(version)
    await db_session.commit()

    # 1. Unfiltered request
    response = await client.get("/api/v1/versions?page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(
        item["id"] == str(ver_id) for item in data["items"]
    )

    # 2. Filtered request
    response_filt = await client.get(
        f"/api/v1/versions?document_id={doc_id}&page=1&size=10"
    )
    assert response_filt.status_code == 200
    data_filt = response_filt.json()
    assert data_filt["total"] == 1
    assert data_filt["items"][0]["id"] == str(ver_id)


@pytest.mark.asyncio
async def test_get_nodes_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /api/v1/nodes/{id} retrieves nodes and returns 404 for invalid IDs."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Test Node Doc")
    db_session.add(doc)

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Content",
    )
    db_session.add(version)
    await db_session.commit()

    node_id = uuid.uuid4()
    node = Node(
        id=node_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="This is a test node content.",
        content_hash=make_hash("This is a test node content."),
        position=0,
    )
    db_session.add(node)
    await db_session.commit()

    # 1. Valid ID
    response = await client.get(f"/api/v1/nodes/{node_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(node_id)
    assert data["node_type"] == "paragraph"
    assert data["content"] == "This is a test node content."

    # 2. Invalid ID
    non_existent = uuid.uuid4()
    response_404 = await client.get(f"/api/v1/nodes/{non_existent}")
    assert response_404.status_code == 404
    assert "not found" in response_404.json()["detail"]


@pytest.mark.asyncio
async def test_search_nodes_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /api/v1/search queries node content successfully."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Test Search Doc")
    db_session.add(doc)

    ver_id = uuid.uuid4()
    version = DocumentVersion(
        id=ver_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Content",
    )
    db_session.add(version)
    await db_session.commit()

    node = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="We are searching for ZebraUniqueKey here.",
        content_hash=make_hash("We are searching for ZebraUniqueKey here."),
        position=0,
    )
    db_session.add(node)
    await db_session.commit()

    # Search ZebraUniqueKey
    response = await client.get("/api/v1/search?q=zebrauniquekey&page=1&size=10")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert "ZebraUniqueKey" in data["items"][0]["content"]


@pytest.mark.asyncio
async def test_get_changes_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /api/v1/changes/{node_id} retrieves node history across versions."""
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Test Change Doc")
    db_session.add(doc)

    v1_id = uuid.uuid4()
    version1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        commit_message="V1",
    )
    v2_id = uuid.uuid4()
    version2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        commit_message="V2",
    )
    db_session.add_all([version1, version2])
    await db_session.commit()

    logical_id = uuid.uuid4()

    # Node in version 1
    node_v1 = Node(
        id=uuid.uuid4(),
        logical_id=logical_id,
        version_id=v1_id,
        node_type="heading",
        content="Original Section",
        content_hash=make_hash("Original Section"),
        position=0,
    )
    # Node in version 2 (modified text!)
    node_v2 = Node(
        id=uuid.uuid4(),
        logical_id=logical_id,
        version_id=v2_id,
        node_type="heading",
        content="Updated Section",
        content_hash=make_hash("Updated Section"),
        position=0,
    )
    db_session.add_all([node_v1, node_v2])
    await db_session.commit()

    response = await client.get(f"/api/v1/changes/{logical_id}")
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    # Verify chronological ordering by version_number
    assert data[0]["version_number"] == 1
    assert data[0]["content"] == "Original Section"

    assert data[1]["version_number"] == 2
    assert data[1]["content"] == "Updated Section"
