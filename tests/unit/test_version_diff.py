import hashlib
import uuid
import pytest

from app.models.sql.node import Node
from app.services.pdf.diff_service import DiffService


def make_hash(text: str) -> str:
    """Helper to generate a SHA-256 hash string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_diff_service_unchanged_and_modified() -> None:
    """Verifies that DiffService correctly classifies unchanged and modified nodes."""
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    # Title node
    n1_title = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="title",
        content="Device Manual",
        content_hash=make_hash("Device Manual"),
        position=0,
        parent_id=None,
    )
    # Heading node (v1)
    n1_h1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="heading",
        content="1. Device Operation",
        content_hash=make_hash("1. Device Operation"),
        position=1,
        parent_id=n1_title.id,
    )
    # Paragraph node (v1)
    n1_p1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="paragraph",
        content="Paragraph content version 1",
        content_hash=make_hash("Paragraph content version 1"),
        position=2,
        parent_id=n1_h1.id,
    )

    # Establish parent-child link for path computation recursion
    n1_title.children = [n1_h1]
    n1_h1.children = [n1_p1]

    # Version 2 Title
    n2_title = Node(
        id=uuid.uuid4(),
        logical_id=n1_title.logical_id,  # Map logical ID
        version_id=v2_id,
        node_type="title",
        content="Device Manual",
        content_hash=make_hash("Device Manual"),
        position=0,
        parent_id=None,
    )
    # Version 2 Heading (unchanged)
    n2_h1 = Node(
        id=uuid.uuid4(),
        logical_id=n1_h1.logical_id,
        version_id=v2_id,
        node_type="heading",
        content="1. Device Operation",
        content_hash=make_hash("1. Device Operation"),
        position=1,
        parent_id=n2_title.id,
    )
    # Version 2 Paragraph (modified content!)
    n2_p1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),  # New temp ID, should copy logical ID from v1 later
        version_id=v2_id,
        node_type="paragraph",
        content="Paragraph content version 2 (edited)",
        content_hash=make_hash("Paragraph content version 2 (edited)"),
        position=2,
        parent_id=n2_h1.id,
    )

    n2_title.children = [n2_h1]
    n2_h1.children = [n2_p1]

    diff_service = DiffService()
    result = diff_service.compare_versions(
        [n1_title, n1_h1, n1_p1], [n2_title, n2_h1, n2_p1]
    )

    # Title and Heading H1 are unchanged
    assert len(result.unchanged) == 2
    unchanged_v2_ids = {pair[1].id for pair in result.unchanged}
    assert n2_title.id in unchanged_v2_ids
    assert n2_h1.id in unchanged_v2_ids

    # Paragraph p1 is modified
    assert len(result.modified) == 1
    assert result.modified[0][0].id == n1_p1.id
    assert result.modified[0][1].id == n2_p1.id


def test_diff_service_added_and_removed() -> None:
    """Verifies that DiffService correctly detects added and removed nodes."""
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    n1_title = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="title",
        content="Doc Title",
        content_hash=make_hash("Doc Title"),
        position=0,
    )
    # Heading to be deleted (in v1, missing in v2)
    n1_h1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="heading",
        content="1. Battery Setup",
        content_hash=make_hash("1. Battery Setup"),
        position=1,
        parent_id=n1_title.id,
    )
    n1_title.children = [n1_h1]

    n2_title = Node(
        id=uuid.uuid4(),
        logical_id=n1_title.logical_id,
        version_id=v2_id,
        node_type="title",
        content="Doc Title",
        content_hash=make_hash("Doc Title"),
        position=0,
    )
    # Heading to be added (missing in v1, in v2)
    n2_h2 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v2_id,
        node_type="heading",
        content="1. Device Cleanup",
        content_hash=make_hash("1. Device Cleanup"),
        position=1,
        parent_id=n2_title.id,
    )
    n2_title.children = [n2_h2]

    diff_service = DiffService()
    result = diff_service.compare_versions([n1_title, n1_h1], [n2_title, n2_h2])

    assert len(result.unchanged) == 1  # Title unchanged
    assert len(result.added) == 1
    assert result.added[0].id == n2_h2.id

    assert len(result.removed) == 1
    assert result.removed[0].id == n1_h1.id


def test_diff_service_renumbering_stability() -> None:
    """Verifies that renumbering section prefixes does not break node identity matching."""
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    # V1 Heading: "3.4 Auto Shutoff"
    n1_h1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v1_id,
        node_type="heading",
        content="3.4 Auto Shutoff",
        content_hash=make_hash("3.4 Auto Shutoff"),
        position=0,
    )

    # V2 Heading: "3.5 Auto Shutoff" (Prefix changed!)
    # Content hash changes because prefix changed, but the logical heading remains the same!
    n2_h1 = Node(
        id=uuid.uuid4(),
        logical_id=uuid.uuid4(),
        version_id=v2_id,
        node_type="heading",
        content="3.5 Auto Shutoff",
        content_hash=make_hash("3.5 Auto Shutoff"),
        position=0,
    )

    diff_service = DiffService()
    result = diff_service.compare_versions([n1_h1], [n2_h1])

    # Since prefix is stripped, both map to path '/Auto Shutoff'
    # Since content text changed ("3.4" vs "3.5"), content_hash changed, so it is classified as MODIFIED (not added/removed)
    assert len(result.modified) == 1
    assert result.modified[0][0].id == n1_h1.id
    assert result.modified[0][1].id == n2_h1.id
    assert len(result.added) == 0
    assert len(result.removed) == 0
