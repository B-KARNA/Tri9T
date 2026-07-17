import uuid
from typing import Any, Dict, List, Tuple

import fitz
import pytest

from app.services.pdf.classifier import ClassifierService
from app.services.pdf.extractor import ExtractorService
from app.services.pdf.models import (
    ParsedDocumentNode,
    ParsedElement,
    ParsedHeading,
    ParsedTable,
)
from app.services.pdf.ocr import OCRService
from app.services.pdf.tree_builder import TreeBuilderService


# --- Realistic Mock Fixtures ---
@pytest.fixture
def classifier() -> ClassifierService:
    return ClassifierService()


@pytest.fixture
def tree_builder() -> TreeBuilderService:
    return TreeBuilderService()


class MockTableContainer:
    """Mock for fitz.table.TableFinder."""

    def __init__(self, tables: List[Any]):
        self.tables = tables


class MockTable:
    """Mock for fitz.table.Table."""

    def __init__(self, bbox: Tuple[float, ...], data: List[List[str]]):
        self.bbox = bbox
        self.data = data

    def extract(self) -> List[List[str]]:
        return self.data


# --- Unit Tests ---


def test_heading_2_1_1_1_fourth_level_node(
    classifier: ClassifierService, tree_builder: TreeBuilderService
) -> None:
    """Verifies that heading '2.1.1.1' parses as level 4 and nests in the fourth tier of the tree."""
    elements = [
        ParsedHeading(
            element_type="heading",
            content="2. Specs",
            page_number=1,
            position=0,
            number_prefix="2",
            level=1,
            title="Specs",
        ),
        ParsedHeading(
            element_type="heading",
            content="2.1 General Specs",
            page_number=1,
            position=1,
            number_prefix="2.1",
            level=2,
            title="General Specs",
        ),
        ParsedHeading(
            element_type="heading",
            content="2.1.1 Battery Specs",
            page_number=1,
            position=2,
            number_prefix="2.1.1",
            level=3,
            title="Battery Specs",
        ),
        ParsedHeading(
            element_type="heading",
            content="2.1.1.1 Battery Life Under Typical Use",
            page_number=1,
            position=3,
            number_prefix="2.1.1.1",
            level=4,
            title="Battery Life Under Typical Use",
        ),
    ]

    # Build hierarchy tree
    root = tree_builder.build_tree(elements)

    # Traverse to level 4 node
    h1 = root.children[0]
    h2 = h1.children[0]
    h3 = h2.children[0]
    h4 = h3.children[0]

    assert h4.element.element_type == "heading"
    assert getattr(h4.element, "level", 1) == 4
    assert getattr(h4.element, "number_prefix", "") == "2.1.1.1"
    assert h4.parent == h3
    assert h3.parent == h2
    assert h2.parent == h1


def test_identical_titles_different_node_ids(
    classifier: ClassifierService,
) -> None:
    """Verifies that two headings with identical text generate unique, distinct UUID node IDs."""
    block1 = {"text": "4.2 Error Codes", "is_bold": True, "font_size": 12.87}
    block2 = {"text": "7.1 Error Codes", "is_bold": True, "font_size": 12.87}

    h1 = classifier.classify_text_block(block1, page_number=4, position=2)
    h2 = classifier.classify_text_block(block2, page_number=6, position=0)

    # Both headings share the same title
    assert getattr(h1, "title") == "Error Codes"
    assert getattr(h2, "title") == "Error Codes"

    # But they must possess unique UUIDs
    assert h1.id != h2.id
    assert isinstance(h1.id, uuid.UUID)
    assert isinstance(h2.id, uuid.UUID)


def test_heading_3_4_before_3_3_preserves_reading_order(
    tree_builder: TreeBuilderService,
) -> None:
    """Verifies that headings appearing out of numerical order preserve their sequential reading order."""
    elements = [
        ParsedHeading(
            element_type="heading",
            content="3. Device Operation",
            page_number=3,
            position=0,
            number_prefix="3",
            level=1,
            title="Device Operation",
        ),
        # 3.4 Auto Shutoff comes BEFORE 3.3 in reading order
        ParsedHeading(
            element_type="heading",
            content="3.4 Auto Shutoff",
            page_number=3,
            position=1,
            number_prefix="3.4",
            level=2,
            title="Auto Shutoff",
        ),
        ParsedHeading(
            element_type="heading",
            content="3.3 Result Display",
            page_number=3,
            position=2,
            number_prefix="3.3",
            level=2,
            title="Result Display",
        ),
    ]

    root = tree_builder.build_tree(elements)
    h1 = root.children[0]

    # Inspect children of H1 (Device Operation)
    assert len(h1.children) == 2
    assert h1.children[0].element.content == "3.4 Auto Shutoff"
    assert h1.children[1].element.content == "3.3 Result Display"

    # Confirm index 0 comes before index 1 in reading order
    assert h1.children[0].element.position < h1.children[1].element.position


def test_tables_extracted_as_table_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that tables are extracted as structured table nodes, removing duplicates."""
    ocr = OCRService()
    extractor = ExtractorService(ocr)

    # Mock page object
    class MockPage:

        def get_text(self, mode: str = "text") -> Any:
            if mode == "dict":
                return {"blocks": []}
            # Non-empty to bypass OCR
            return "Some page content"

        def find_tables(self) -> Any:
            # Provide two overlapping tables to test deduplication
            t1 = MockTable(
                bbox=(10, 10, 100, 100),
                data=[["Header1", "Header2"], ["Val1", "Val2"]],
            )
            t2 = MockTable(
                bbox=(15, 15, 80, 80),  # Completely inside t1
                data=[["Val1", "Val2"]],
            )
            return MockTableContainer([t1, t2])

    mock_page = MockPage()
    elements = extractor.extract_page_elements(mock_page, page_number=2)

    # Exactly 1 table element should survive deduplication (the enclosing Table 1)
    table_elements = [el for el in elements if isinstance(el, ParsedTable)]
    assert len(table_elements) == 1

    extracted_table = table_elements[0]
    assert extracted_table.element_type == "table"
    assert extracted_table.headers == ["Header1", "Header2"]
    assert extracted_table.rows == [["Val1", "Val2"]]


def test_ordered_lists_not_mistaken_for_headings(
    classifier: ClassifierService,
) -> None:
    """Verifies that ordered list items are classified correctly and not mistaken for headings."""
    # Bold sequence = Heading
    heading_block = {
        "text": "1. Device Overview",
        "is_bold": True,
        "font_size": 16.5,
    }

    # Regular sequence = List Item
    list_block = {
        "text": "1. Normal: systolic < 120",
        "is_bold": False,
        "font_size": 11.0,
    }

    el_heading = classifier.classify_text_block(
        heading_block, page_number=1, position=1
    )
    el_list = classifier.classify_text_block(
        list_block, page_number=3, position=5
    )

    assert el_heading.element_type == "heading"
    assert isinstance(el_heading, ParsedHeading)

    assert el_list.element_type == "ordered_list_item"
    assert not isinstance(el_list, ParsedHeading)
