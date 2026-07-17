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
async def test_qa_traceability_lifecycle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verifies that the qa-traceability endpoint correctly returns Fresh, Possibly stale, and Stale statuses."""
    # 1. Setup Document, Version 1
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, name="Traceability Manual")
    db_session.add(doc)

    v1_id = uuid.uuid4()
    version1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        commit_message="Initial Ingestion",
    )
    db_session.add(version1)
    await db_session.commit()

    # Create 3 logical nodes in Version 1
    node_fresh_v1_id = uuid.uuid4()
    logical_fresh = uuid.uuid4()
    node_fresh_v1 = Node(
        id=node_fresh_v1_id,
        logical_id=logical_fresh,
        version_id=v1_id,
        node_type="paragraph",
        content="This content is unchanged.",
        content_hash=make_hash("This content is unchanged."),
        position=0,
    )

    node_mod_v1_id = uuid.uuid4()
    logical_mod = uuid.uuid4()
    node_mod_v1 = Node(
        id=node_mod_v1_id,
        logical_id=logical_mod,
        version_id=v1_id,
        node_type="paragraph",
        content="This content will change.",
        content_hash=make_hash("This content will change."),
        position=1,
    )

    node_del_v1_id = uuid.uuid4()
    logical_del = uuid.uuid4()
    node_del_v1 = Node(
        id=node_del_v1_id,
        logical_id=logical_del,
        version_id=v1_id,
        node_type="paragraph",
        content="This content will be deleted.",
        content_hash=make_hash("This content will be deleted."),
        position=2,
    )

    db_session.add_all([node_fresh_v1, node_mod_v1, node_del_v1])
    await db_session.commit()

    # 2. Setup Selections and Test Cases pinned to Version 1 nodes
    # Selection 1: mapped to Node Fresh
    sel_fresh_id = uuid.uuid4()
    sel_fresh = Selection(id=sel_fresh_id, document_id=doc_id, version_id=v1_id)
    db_session.add(sel_fresh)
    await db_session.flush()

    db_session.add(SelectionNodeMapping(selection_id=sel_fresh_id, node_id=node_fresh_v1_id))
    db_session.add(
        GeneratedTestCase(
            id=uuid.uuid4(),
            selection_id=sel_fresh_id,
            version_id=v1_id,
            question="Unchanged query?",
            answer="Unchanged answer.",
            referenced_node_ids=[str(node_fresh_v1_id)],
            referenced_content_hashes={str(node_fresh_v1_id): node_fresh_v1.content_hash},
        )
    )

    # Selection 2: mapped to Node Modified
    sel_mod_id = uuid.uuid4()
    sel_mod = Selection(id=sel_mod_id, document_id=doc_id, version_id=v1_id)
    db_session.add(sel_mod)
    await db_session.flush()

    db_session.add(SelectionNodeMapping(selection_id=sel_mod_id, node_id=node_mod_v1_id))
    db_session.add(
        GeneratedTestCase(
            id=uuid.uuid4(),
            selection_id=sel_mod_id,
            version_id=v1_id,
            question="Changing query?",
            answer="Changing answer.",
            referenced_node_ids=[str(node_mod_v1_id)],
            referenced_content_hashes={str(node_mod_v1_id): node_mod_v1.content_hash},
        )
    )

    # Selection 3: mapped to Node Deleted
    sel_del_id = uuid.uuid4()
    sel_del = Selection(id=sel_del_id, document_id=doc_id, version_id=v1_id)
    db_session.add(sel_del)
    await db_session.flush()

    db_session.add(SelectionNodeMapping(selection_id=sel_del_id, node_id=node_del_v1_id))
    db_session.add(
        GeneratedTestCase(
            id=uuid.uuid4(),
            selection_id=sel_del_id,
            version_id=v1_id,
            question="Deleted query?",
            answer="Deleted answer.",
            referenced_node_ids=[str(node_del_v1_id)],
            referenced_content_hashes={str(node_del_v1_id): node_del_v1.content_hash},
        )
    )

    await db_session.commit()

    # 3. Simulate Ingestion of Version 2
    v2_id = uuid.uuid4()
    version2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        commit_message="Second Ingestion",
    )
    db_session.add(version2)
    await db_session.commit()

    # Node Fresh: exists in V2, same hash
    node_fresh_v2 = Node(
        id=uuid.uuid4(),
        logical_id=logical_fresh,
        version_id=v2_id,
        node_type="paragraph",
        content="This content is unchanged.",
        content_hash=make_hash("This content is unchanged."),
        position=0,
    )
    # Node Modified: exists in V2, different hash
    node_mod_v2 = Node(
        id=uuid.uuid4(),
        logical_id=logical_mod,
        version_id=v2_id,
        node_type="paragraph",
        content="This content HAS changed.",
        content_hash=make_hash("This content HAS changed."),
        position=1,
    )
    # Node Deleted: DOES NOT EXIST in V2! (logical_del is missing)

    db_session.add_all([node_fresh_v2, node_mod_v2])
    await db_session.commit()

    # 4. Check Traceability for Selection 1 (Fresh)
    res_fresh = await client.get(
        f"/api/v1/selection/{sel_fresh_id}/qa-traceability?target_version_id={v2_id}"
    )
    assert res_fresh.status_code == 200
    data_fresh = res_fresh.json()
    assert data_fresh["results"][0]["status"] == "Fresh"
    assert "hashes match" in data_fresh["results"][0]["reason"]

    # 5. Check Traceability for Selection 2 (Possibly stale)
    res_mod = await client.get(
        f"/api/v1/selection/{sel_mod_id}/qa-traceability?target_version_id={v2_id}"
    )
    assert res_mod.status_code == 200
    data_mod = res_mod.json()
    assert data_mod["results"][0]["status"] == "Possibly stale"
    assert "was modified" in data_mod["results"][0]["reason"]

    # 6. Check Traceability for Selection 3 (Stale)
    res_del = await client.get(
        f"/api/v1/selection/{sel_del_id}/qa-traceability?target_version_id={v2_id}"
    )
    assert res_del.status_code == 200
    data_del = res_del.json()
    assert data_del["results"][0]["status"] == "Stale"
    assert "was deleted" in data_del["results"][0]["reason"]
