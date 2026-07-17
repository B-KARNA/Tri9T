import os

import pytest

from app.services.pdf.models import ParsedHeading, ParsedTable
from app.services.pdf.parser import PDFParserService


def test_pdf_parser_pipeline() -> None:
    """Verifies that the PDF parsing pipeline correctly extracts hierarchy, tables, lists, and headings."""
    pdf_path = r"C:\Users\bkarn\OneDrive\Desktop\Tri9T\ct200_manual.pdf"
    assert os.path.exists(pdf_path), f"Target manual not found at {pdf_path}"

    parser = PDFParserService()
    tree = parser.parse_pdf(pdf_path)

    # 1. Root structure verification
    assert tree.element.element_type == "document"

    # 2. Document Title extraction verification
    title_nodes = [
        child for child in tree.children if child.element.element_type == "title"
    ]
    assert len(title_nodes) == 1
    assert "CardioTrack CT-200" in title_nodes[0].element.content

    # 3. Headings extraction and hierarchical leveling (2.1.1.1)
    headings: List[ParsedHeading] = []

    def collect_headings(node) -> None:
        if node.element.element_type == "heading":
            headings.append(node.element)
        for child in node.children:
            collect_headings(child)

    collect_headings(tree)

    heading_titles = [h.title for h in headings]
    assert "Device Overview" in heading_titles
    assert "Battery Life Under Typical Use" in heading_titles

    # Verify battery life heading is level 4 (2.1.1.1)
    battery_life_hd = [
        h for h in headings if h.title == "Battery Life Under Typical Use"
    ]
    assert len(battery_life_hd) == 1
    assert battery_life_hd[0].level == 4
    assert battery_life_hd[0].number_prefix == "2.1.1.1"

    # 4. Out of numerical order headings (3.4 Auto Shutoff before 3.3 Result Display)
    device_op_node = None

    def find_node(node, title: str):
        if (
            isinstance(node.element, ParsedHeading)
            and node.element.title == title
        ):
            return node
        for child in node.children:
            found = find_node(child, title)
            if found:
                return found
        return None

    device_op_node = find_node(tree, "Device Operation")
    assert device_op_node is not None

    child_heading_titles = [
        child.element.title
        for child in device_op_node.children
        if child.element.element_type == "heading"
    ]

    # Verify 3.4 appears BEFORE 3.3 in reading order, but nested under same parent
    assert "Auto Shutoff" in child_heading_titles
    assert "Result Display and Classification" in child_heading_titles

    idx_3_4 = child_heading_titles.index("Auto Shutoff")
    idx_3_3 = child_heading_titles.index("Result Display and Classification")
    assert (
        idx_3_4 < idx_3_3
    ), "Heading 3.4 must appear before 3.3 to preserve reading order."

    # 5. Table Extraction and Bounding Box Deduplication
    tables: List[ParsedTable] = []

    def collect_tables(node) -> None:
        if node.element.element_type == "table":
            tables.append(node.element)
        for child in node.children:
            collect_tables(child)

    collect_tables(tree)

    # Valid tables: Table 1 (Specifications) on Page 2 and Table 2 (Error Codes) on Page 4
    # All sub-fragments should have been filtered out by bounding box containment checks
    assert len(tables) == 2, f"Expected 2 tables, found {len(tables)}."

    # Table 1 Assertions
    assert "Parameter" in tables[0].headers
    assert "Value" in tables[0].headers
    assert any("Measurement method" in row for row in tables[0].rows)

    # Table 2 Assertions
    assert "Code" in tables[1].headers
    assert "Meaning" in tables[1].headers
    assert any("E1" in row for row in tables[1].rows)

    # 6. List Items extraction (Ordered List)
    list_items = []

    def collect_list_items(node) -> None:
        if node.element.element_type in [
            "ordered_list_item",
            "unordered_list_item",
        ]:
            list_items.append(node.element)
        for child in node.children:
            collect_list_items(child)

    collect_list_items(tree)

    # The result classification list has 5 ordered list items on page 3
    assert len(list_items) >= 5
    assert any("Normal:" in item.content for item in list_items)
