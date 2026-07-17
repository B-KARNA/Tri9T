import hashlib
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.document import Document, DocumentVersion
from app.models.sql.node import Node
from app.models.sql.selection import Selection, SelectionNodeMapping
from app.models.sql.qa_test_case import GeneratedTestCase


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_retrieval_apis_flow(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Tests GET /generation/{selection_id} and GET /generation/node/{node_id} endpoints."""
    # 1. Setup Version 1
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="CT-200 Technical Specs")
    db_session.add(doc)

    v1_id = uuid.uuid4()
    version1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Specs V1",
    )
    db_session.add(version1)
    await db_session.commit()

    n_id = uuid.uuid4()
    logical_id = uuid.uuid4()
    node_v1 = Node(
        id=n_id,
        logical_id=logical_id,
        version_id=v1_id,
        node_type="paragraph",
        content="System power supply is 24V DC.",
        content_hash=make_hash("System power supply is 24V DC."),
        position=0,
    )
    db_session.add(node_v1)
    await db_session.commit()

    sel_id = uuid.uuid4()
    selection = Selection(id=sel_id, document_id=doc_id, version_id=v1_id)
    db_session.add(selection)
    await db_session.flush()

    db_session.add(SelectionNodeMapping(selection_id=sel_id, node_id=n_id))
    db_session.add(
        GeneratedTestCase(
            id=uuid.uuid4(),
            selection_id=sel_id,
            version_id=v1_id,
            question="What is the system power supply voltage?",
            answer="24V DC.",
            referenced_node_ids=[str(n_id)],
            referenced_content_hashes={str(n_id): node_v1.content_hash},
        )
    )
    await db_session.commit()

    # 2. Setup Version 2 (Modified text!)
    v2_id = uuid.uuid4()
    version2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        commit_message="Specs V2 (voltage update)",
    )
    db_session.add(version2)
    await db_session.commit()

    node_v2 = Node(
        id=uuid.uuid4(),
        logical_id=logical_id,
        version_id=v2_id,
        node_type="paragraph",
        content="System power supply is 12V DC.",  # 24V -> 12V
        content_hash=make_hash("System power supply is 12V DC."),
        position=0,
    )
    db_session.add(node_v2)
    await db_session.commit()

    # 3. Test GET /generation/{selection_id}
    res_sel = await client.get(f"/api/v1/generation/{sel_id}")
    assert res_sel.status_code == 200
    data_sel = res_sel.json()

    assert data_sel["selection_id"] == str(sel_id)
    assert data_sel["original_version"]["version_number"] == 1
    assert data_sel["current_version"]["version_number"] == 2
    assert data_sel["staleness_status"] == "Possibly stale"

    tcs = data_sel["test_cases"]
    assert len(tcs) == 1
    assert tcs[0]["status"] == "Possibly stale"
    # Verify diff shows up in the summary
    assert "-System power supply is 24V DC." in tcs[0]["diff_summary"]
    assert "+System power supply is 12V DC." in tcs[0]["diff_summary"]

    # 4. Test GET /generation/node/{node_id}
    res_node = await client.get(f"/api/v1/generation/node/{logical_id}")
    assert res_node.status_code == 200
    data_node = res_node.json()

    assert isinstance(data_node, list)
    assert len(data_node) == 1
    assert data_node[0]["selection_id"] == str(sel_id)
    assert data_node[0]["staleness_status"] == "Possibly stale"

    # 5. Test 404 conditions
    bad_id = uuid.uuid4()
    res_404_sel = await client.get(f"/api/v1/generation/{bad_id}")
    assert res_404_sel.status_code == 404

    res_404_node = await client.get(f"/api/v1/generation/node/{bad_id}")
    assert res_404_node.status_code == 404
