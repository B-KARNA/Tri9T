from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

import fitz

from app.core.logging import logger
from app.services.pdf.models import ParsedElement, ParsedTable
from app.services.pdf.ocr import OCRService


def normalize_text(text: str) -> str:
    """Replaces Unicode ligatures and smart quotes with standard equivalents."""
    replacements = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\ufb05": "ft",
        "\ufb06": "st",
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2013": "-",
        "\u2014": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


class ExtractorService:
    """Extracts raw text blocks (with font attributes) and tables from PDF pages, preserving reading order."""

    def __init__(self, ocr_service: OCRService):
        self.ocr_service = ocr_service

    def extract_page_elements(
        self, page: fitz.Page, page_number: int
    ) -> List[Union[Dict[str, Any], ParsedElement]]:
        """Parses a single page into reading-ordered text blocks and ParsedTable structures."""
        text_check = page.get_text().strip()

        # Check if page is empty of selectable text, indicating scanned/image-only content
        if not text_check:
            logger.info(
                "No selectable text found on page. Falling back to OCR.",
                page=page_number,
            )
            pix = page.get_pixmap()
            ocr_text = self.ocr_service.perform_ocr(pix)

            elements: List[Union[Dict[str, Any], ParsedElement]] = []
            blocks = ocr_text.split("\n\n")
            for pos, block in enumerate(blocks):
                clean = normalize_text(block.strip())
                if clean:
                    elements.append(
                        {
                            "type": "text_block",
                            "text": clean,
                            "bbox": (0, 0, 0, 0),
                            "is_bold": False,
                            "font_size": 11.0,
                            "position": pos,
                        }
                    )
            return elements

        # 1. Extract and deduplicate tables on the page
        tables = page.find_tables()
        valid_tables: List[fitz.table.Table] = []

        # Sort tables by bounding box area (descending) to resolve parent containers first
        sorted_tables = sorted(
            tables.tables,
            key=lambda t: (t.bbox[2] - t.bbox[0]) * (t.bbox[3] - t.bbox[1]),
            reverse=True,
        )

        for t in sorted_tables:
            is_inside = False
            for vt in valid_tables:
                vtx0, vty0, vtx1, vty1 = vt.bbox
                tx0, ty0, tx1, ty1 = t.bbox
                # Check if table 't' is fully enclosed in table 'vt' (with 5pt tolerance)
                if (
                    tx0 >= vtx0 - 5
                    and ty0 >= vty0 - 5
                    and tx1 <= vtx1 + 5
                    and ty1 <= vty1 + 5
                ):
                    is_inside = True
                    break
            if not is_inside:
                valid_tables.append(t)

        parsed_tables: List[Dict[str, Any]] = []
        for t_idx, t in enumerate(valid_tables):
            extracted = t.extract()
            if extracted:
                # First row represents headers, the rest are data rows
                headers = [normalize_text(h or "") for h in extracted[0]]
                rows = [
                    [normalize_text(cell or "") for cell in row]
                    for row in extracted[1:]
                ]

                # Format content representation
                content_str = (
                    f"Table {t_idx+1}: " + " | ".join(headers) + "\n"
                )
                content_str += "\n".join(" | ".join(row) for row in rows)

                parsed_tables.append(
                    {
                        "element": ParsedTable(
                            element_type="table",
                            content=content_str,
                            page_number=page_number,
                            headers=headers,
                            rows=rows,
                        ),
                        "bbox": t.bbox,
                    }
                )

        # 2. Extract text blocks and filter out blocks that lie inside table coordinates
        page_dict = page.get_text("dict")
        raw_blocks = page_dict.get("blocks", [])
        extracted_text_blocks: List[Dict[str, Any]] = []

        for block in raw_blocks:
            # We only process text blocks (type 0)
            if block.get("type") != 0:
                continue

            bbox = block["bbox"]

            # Filter out block if its center or main area lies within any table bounding box
            is_inside_table = False
            bx0, by0, bx1, by1 = bbox
            for pt in parsed_tables:
                tx0, ty0, tx1, ty1 = pt["bbox"]
                if (
                    bx0 >= tx0 - 5
                    and by0 >= ty0 - 5
                    and bx1 <= tx1 + 5
                    and by1 <= ty1 + 5
                ):
                    is_inside_table = True
                    break

            if is_inside_table:
                continue

            # Concatenate lines and gather styling attributes
            block_text = ""
            is_bold = False
            max_font_size = 0.0

            for line in block.get("lines", []):
                line_text = ""
                for span in line.get("spans", []):
                    line_text += span["text"]
                    font_name = span.get("font", "").lower()
                    flags = span.get("flags", 0)

                    # Determine if bold (checking flags & 16 or name containing bold)
                    if "bold" in font_name or bool(flags & 16):
                        is_bold = True

                    max_font_size = max(max_font_size, span.get("size", 11.0))
                block_text += line_text + "\n"

            clean_text = normalize_text(block_text.strip())
            if clean_text:
                extracted_text_blocks.append(
                    {
                        "type": "text_block",
                        "text": clean_text,
                        "bbox": bbox,
                        "is_bold": is_bold,
                        "font_size": max_font_size,
                    }
                )

        # 3. Merge tables and text blocks using their vertical coordinates (y0) to preserve reading order
        merged_items: List[
            Tuple[float, Union[Dict[str, Any], Dict[str, Any]]]
        ] = []

        for tb in extracted_text_blocks:
            merged_items.append((tb["bbox"][1], tb))

        for pt in parsed_tables:
            merged_items.append((pt["bbox"][1], pt))

        # Sort top-to-bottom
        merged_items.sort(key=lambda x: x[0])

        results: List[Union[Dict[str, Any], ParsedElement]] = []
        for _, item in merged_items:
            if "element" in item:
                # It's a table
                results.append(item["element"])
            else:
                # It's a text block dictionary
                results.append(item)

        return results
