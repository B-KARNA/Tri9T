import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.document import Document, DocumentVersion
from app.models.sql.node import Node
from app.models.sql.selection import Selection


def make_hash(text: str) -> str:
    """Helper to generate a SHA-256 hash string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_create_and_get_selection_flow(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests POST /selection creates highlights and GET /selection/{id} retrieves them successfully."""
    # 1. Setup Document, Version, and Nodes
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="CT-200 Guide")
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

    n1_id = uuid.uuid4()
    n2_id = uuid.uuid4()

    node1 = Node(
        id=n1_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="heading",
        content="1. Operating Instructions",
        content_hash=make_hash("1. Operating Instructions"),
        position=0,
    )
    node2 = Node(
        id=n2_id,
        logical_id=uuid.uuid4(),
        version_id=ver_id,
        node_type="paragraph",
        content="Press the button.",
        content_hash=make_hash("Press the button."),
        position=1,
    )
    db_session.add_all([node1, node2])
    await db_session.commit()

    # 2. Test successful selection creation (POST /selection)
    payload = {
        "version_id": str(ver_id),
        "node_ids": [str(n1_id), str(n2_id)],
        "name": "User Highlight 1",
    }
    response = await client.post("/api/v1/selection", json=payload)
    assert response.status_code == 201
    data = response.json()

    sel_id = data["id"]
    assert data["version_id"] == str(ver_id)
    assert data["document_id"] == str(doc_id)
    assert data["name"] == "User Highlight 1"
    assert set(data["node_ids"]) == {str(n1_id), str(n2_id)}

    # 3. Test successful selection retrieval (GET /selection/{id})
    response_get = await client.get(f"/api/v1/selection/{sel_id}")
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["id"] == sel_id
    assert data_get["version_id"] == str(ver_id)
    assert set(data_get["node_ids"]) == {str(n1_id), str(n2_id)}


@pytest.mark.asyncio
async def test_create_selection_validation_errors(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests POST /selection error states (invalid version, missing nodes, version mismatches)."""
    # Setup standard records
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Specs doc")
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

    n1_v1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="paragraph",
        content="V1 text",
        content_hash=make_hash("V1 text"),
        position=0,
    )
    n2_v2 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v2_id,
        node_type="paragraph",
        content="V2 text",
        content_hash=make_hash("V2 text"),
        position=0,
    )
    db_session.add_all([n1_v1, n2_v2])
    await db_session.commit()

    # 1. Invalid version ID (404)
    bad_ver = uuid.uuid4()
    response_404 = await client.post(
        "/api/v1/selection",
        json={"version_id": str(bad_ver), "node_ids": [str(n1_v1.id)]},
    )
    assert response_404.status_code == 404
    assert "not found" in response_404.json()["detail"].lower()

    # 2. Missing node IDs (400)
    response_empty = await client.post(
        "/api/v1/selection",
        json={"version_id": str(v1_id), "node_ids": []},
    )
    assert response_empty.status_code == 400
    assert "at least one node ID" in response_empty.json()["detail"]

    # 3. Mismatched version nodes (400)
    # n2_v2 belongs to version 2, but we pass version 1
    response_mix = await client.post(
        "/api/v1/selection",
        json={"version_id": str(v1_id), "node_ids": [str(n2_v2.id)]},
    )
    assert response_mix.status_code == 400
    assert "invalid or do not belong to version" in response_mix.json()["detail"]


@pytest.mark.asyncio
async def test_selections_remain_immutable_after_reingestion(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verifies that selections remain pinned to their original version nodes, unaffected by new document ingestions."""
    # 1. Setup Document, Version 1, and Nodes
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Reingestion Guide")
    db_session.add(doc)

    v1_id = uuid.uuid4()
    version1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Initial ingestion",
    )
    db_session.add(version1)
    await db_session.commit()

    n1_v1_id = uuid.uuid4()
    node_v1 = Node(
        id=n1_v1_id,
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="paragraph",
        content="Selectable text",
        content_hash=make_hash("Selectable text"),
        position=0,
    )
    db_session.add(node_v1)
    await db_session.commit()

    # 2. Create selection pinned to Version 1 node
    payload = {
        "version_id": str(v1_id),
        "node_ids": [str(n1_v1_id)],
        "name": "Version 1 Highlight",
    }
    response_create = await client.post("/api/v1/selection", json=payload)
    assert response_create.status_code == 201
    sel_id = response_create.json()["id"]

    # 3. Simulate Document Re-ingestion (creates Version 2 with new Node rows)
    v2_id = uuid.uuid4()
    version2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        commit_message="Re-ingested version",
    )
    db_session.add(version2)
    await db_session.commit()

    n1_v2_id = uuid.uuid4()
    node_v2 = Node(
        id=n1_v2_id,
        logical_id=node_v1.logical_id,  # Matches logical ID (same node conceptually)
        version_id=v2_id,
        node_type="paragraph",
        content="Selectable text (updated content)",
        content_hash=make_hash("Selectable text (updated content)"),
        position=0,
    )
    db_session.add(node_v2)
    await db_session.commit()

    # 4. Retrieve selection and assert immutability
    response_get = await client.get(f"/api/v1/selection/{sel_id}")
    assert response_get.status_code == 200
    selection_data = response_get.json()

    # Confirm selection continues to reference Version 1 (v1_id) and the original node UUID (n1_v1_id)
    # It does not shift or automatically mutate to Version 2
    assert selection_data["version_id"] == str(v1_id)
    assert selection_data["node_ids"] == [str(n1_v1_id)]
    assert selection_data["node_ids"] != [str(n1_v2_id)]
