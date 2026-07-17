import hashlib
import uuid
from typing import Dict, Set

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sql.document import Document, DocumentVersion
from app.models.sql.node import Node
from app.models.sql.selection import Selection, SelectionNodeMapping

pytestmark = pytest.mark.asyncio


def get_hash(content: str) -> str:
    """Helper to calculate SHA-256 content hashes."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def test_document_and_versioning(db_session: AsyncSession) -> None:
    """Verifies that a document can have multiple chronological versions."""
    # 1. Create a Document
    doc = Document(name="Product Requirements Doc")
    db_session.add(doc)
    await db_session.flush()

    # 2. Add Versions
    v1 = DocumentVersion(
        document_id=doc.id, version_number=1, commit_message="Initial draft"
    )
    v2 = DocumentVersion(
        document_id=doc.id, version_number=2, commit_message="Incorporate feed"
    )
    db_session.add_all([v1, v2])
    await db_session.flush()

    # Refresh document
    await db_session.refresh(doc)

    assert len(doc.versions) == 2
    assert doc.versions[0].version_number == 1
    assert doc.versions[1].version_number == 2


async def test_parent_child_hierarchy(db_session: AsyncSession) -> None:
    """Verifies parent-child relationships and sibling order positions."""
    # Create baseline doc/version
    doc = Document(name="Hierarchy Doc")
    db_session.add(doc)
    await db_session.flush()
    v1 = DocumentVersion(document_id=doc.id, version_number=1)
    db_session.add(v1)
    await db_session.flush()

    # Create root node
    root = Node(
        version_id=v1.id,
        node_type="document",
        content="Root Document",
        content_hash=get_hash("Root Document"),
        position=0,
    )
    db_session.add(root)
    await db_session.flush()

    # Create children under root
    child1 = Node(
        version_id=v1.id,
        parent_id=root.id,
        node_type="section",
        content="Introduction Section",
        content_hash=get_hash("Introduction Section"),
        position=1,
    )
    child2 = Node(
        version_id=v1.id,
        parent_id=root.id,
        node_type="section",
        content="Technical Plan Section",
        content_hash=get_hash("Technical Plan Section"),
        position=2,
    )
    db_session.add_all([child1, child2])
    await db_session.flush()

    # Refresh root to inspect loaded relationships
    await db_session.refresh(root)

    assert len(root.children) == 2
    assert root.children[0].content == "Introduction Section"
    assert root.children[1].content == "Technical Plan Section"
    assert root.children[0].parent_id == root.id


async def test_stable_logical_identity_and_diff(
    db_session: AsyncSession,
) -> None:
    """Verifies stable logical node identity and demonstrates diffing versions.

    Ensures we can compare two versions and correctly resolve:
      - Unchanged nodes
      - Modified nodes (same logical_id, changed hash)
      - Added nodes (new logical_id in newer version)
      - Deleted nodes (logical_id present in old but missing in new)
    """
    # Create doc
    doc = Document(name="Diffing Doc")
    db_session.add(doc)
    await db_session.flush()

    # Create v1 and v2 records
    v1 = DocumentVersion(document_id=doc.id, version_number=1)
    v2 = DocumentVersion(document_id=doc.id, version_number=2)
    db_session.add_all([v1, v2])
    await db_session.flush()

    # Generate logical identities
    logical_unchanged = uuid.uuid4()
    logical_modified = uuid.uuid4()
    logical_deleted = uuid.uuid4()
    logical_added = uuid.uuid4()

    # --- VERSION 1 NODES ---
    v1_unchanged = Node(
        logical_id=logical_unchanged,
        version_id=v1.id,
        node_type="paragraph",
        content="Unchanged text",
        content_hash=get_hash("Unchanged text"),
        position=0,
    )
    v1_modified = Node(
        logical_id=logical_modified,
        version_id=v1.id,
        node_type="paragraph",
        content="Original modified text",
        content_hash=get_hash("Original modified text"),
        position=1,
    )
    v1_deleted = Node(
        logical_id=logical_deleted,
        version_id=v1.id,
        node_type="paragraph",
        content="Deleted paragraph text",
        content_hash=get_hash("Deleted paragraph text"),
        position=2,
    )
    db_session.add_all([v1_unchanged, v1_modified, v1_deleted])

    # --- VERSION 2 NODES ---
    v2_unchanged = Node(
        logical_id=logical_unchanged,
        version_id=v2.id,
        node_type="paragraph",
        content="Unchanged text",
        content_hash=get_hash("Unchanged text"),  # Hash is identical
        position=0,
    )
    v2_modified = Node(
        logical_id=logical_modified,
        version_id=v2.id,
        node_type="paragraph",
        content="New updated text",  # Content is changed
        content_hash=get_hash("New updated text"),  # Hash is changed
        position=1,
    )
    v2_added = Node(
        logical_id=logical_added,
        version_id=v2.id,
        node_type="paragraph",
        content="Fresh new text",
        content_hash=get_hash("Fresh new text"),
        position=2,
    )
    db_session.add_all([v2_unchanged, v2_modified, v2_added])
    await db_session.flush()

    # --- DIFF ENGINE SIMULATION ---
    # Query all nodes for Version 1 and Version 2
    stmt_v1 = select(Node).where(Node.version_id == v1.id)
    v1_nodes = (await db_session.execute(stmt_v1)).scalars().all()

    stmt_v2 = select(Node).where(Node.version_id == v2.id)
    v2_nodes = (await db_session.execute(stmt_v2)).scalars().all()

    # Build maps of logical_id -> node
    v1_map: Dict[uuid.UUID, Node] = {n.logical_id: n for n in v1_nodes}
    v2_map: Dict[uuid.UUID, Node] = {n.logical_id: n for n in v2_nodes}

    # Compare logical IDs
    all_logical_ids: Set[uuid.UUID] = set(v1_map.keys()).union(v2_map.keys())

    added_ids = []
    deleted_ids = []
    modified_ids = []
    unchanged_ids = []

    for lid in all_logical_ids:
        in_v1 = lid in v1_map
        in_v2 = lid in v2_map

        if in_v1 and not in_v2:
            deleted_ids.append(lid)
        elif in_v2 and not in_v1:
            added_ids.append(lid)
        else:
            # Present in both, check content hashes
            if v1_map[lid].content_hash != v2_map[lid].content_hash:
                modified_ids.append(lid)
            else:
                unchanged_ids.append(lid)

    assert added_ids == [logical_added]
    assert deleted_ids == [logical_deleted]
    assert modified_ids == [logical_modified]
    assert unchanged_ids == [logical_unchanged]


async def test_version_pinned_selections(db_session: AsyncSession) -> None:
    """Verifies that selections are locked to specific document versions."""
    # Create doc
    doc = Document(name="Selection Doc")
    db_session.add(doc)
    await db_session.flush()

    # Create v1 record
    v1 = DocumentVersion(document_id=doc.id, version_number=1)
    db_session.add(v1)
    await db_session.flush()

    # Create node
    node = Node(
        version_id=v1.id,
        node_type="paragraph",
        content="Testing highlight annotations",
        content_hash=get_hash("Testing highlight annotations"),
        position=0,
    )
    db_session.add(node)
    await db_session.flush()

    # Create Selection pinned to v1
    selection = Selection(
        document_id=doc.id, version_id=v1.id, name="Important Highlight"
    )
    db_session.add(selection)
    await db_session.flush()

    # Map Selection to Node
    mapping = SelectionNodeMapping(
        selection_id=selection.id,
        node_id=node.id,
        anchor_offset=8,
        focus_offset=17,
    )
    db_session.add(mapping)
    await db_session.flush()

    # Verify relationships
    await db_session.refresh(selection)
    assert len(selection.node_mappings) == 1
    assert selection.node_mappings[0].node_id == node.id
    assert selection.node_mappings[0].anchor_offset == 8
    assert selection.node_mappings[0].focus_offset == 17
