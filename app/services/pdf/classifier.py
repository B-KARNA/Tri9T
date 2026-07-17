from __future__ import annotations

import re
from typing import Any, Dict, List

from app.services.pdf.models import ParsedElement, ParsedHeading


class ClassifierService:
    """Classifies raw text blocks into structured document elements using text patterns and font properties."""

    # Matches numbered headings: "1. Device Overview", "2.1.1.1 Battery Life"
    HEADING_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+)$", re.DOTALL)

    # Matches ordered lists: "1. Normal", "a. Item", "(1) Item", "1) Item"
    ORDERED_LIST_PATTERN = re.compile(
        r"^\s*(?:\d+|[a-zA-Z]|[ivxIVX]+)\.?\)\s+(.+)$|^\s*(?:\d+|[a-zA-Z]|[ivxIVX]+)\.\s+(.+)$",
        re.DOTALL,
    )

    # Matches bullets: "• Item", "- Item", "* Item"
    UNORDERED_LIST_PATTERN = re.compile(
        r"^\s*([•\-\*\u2022\u2043\u2219\u25e6])\s*(.+)$", re.DOTALL
    )

    def classify_text_block(
        self, block: Dict[str, Any], page_number: int, position: int
    ) -> ParsedElement:
        """Determines the semantic element type of a text block."""
        text = block["text"].strip()
        is_bold = block["is_bold"]
        font_size = block["font_size"]

        # 1. Document Title: First large bold block on the first page
        if page_number == 1 and position == 0 and (font_size > 20 or is_bold):
            return ParsedElement(
                element_type="title",
                content=text,
                page_number=page_number,
                position=position,
            )

        # 2. Heading: Matches numbering sequence AND is in a bold font
        heading_match = self.HEADING_PATTERN.match(text)
        if heading_match and is_bold:
            prefix = heading_match.group(1)
            title_text = heading_match.group(2).strip().replace("\n", " ")
            clean_prefix = prefix.rstrip(".")
            # Compute heading depth based on dot splits: e.g. "2.1.1.1" -> level 4
            level = len(clean_prefix.split("."))
            return ParsedHeading(
                element_type="heading",
                content=text,
                page_number=page_number,
                position=position,
                number_prefix=prefix,
                level=level,
                title=title_text,
                is_ambiguous=False,
            )
        elif is_bold and font_size >= 11.0:
            # Unnumbered heading detection
            level = None
            is_ambiguous = False

            if font_size >= 16.0:
                level = 1
            elif font_size >= 12.5:
                level = 2
            elif font_size == 11.0:
                level = 3
                is_ambiguous = True  # Ambiguous because 11.0 is also standard body text size
            else:
                level = 2
                is_ambiguous = True

            return ParsedHeading(
                element_type="heading",
                content=text,
                page_number=page_number,
                position=position,
                number_prefix=None,
                level=level,
                title=text,
                is_ambiguous=is_ambiguous,
            )

        # 3. Ordered list item: Matches numbering/letter bullet, but is NOT bold
        ordered_match = self.ORDERED_LIST_PATTERN.match(text)
        if ordered_match and not is_bold:
            return ParsedElement(
                element_type="ordered_list_item",
                content=text,
                page_number=page_number,
                position=position,
            )

        # 4. Unordered list item: Matches standard bullet points
        unordered_match = self.UNORDERED_LIST_PATTERN.match(text)
        if unordered_match:
            return ParsedElement(
                element_type="unordered_list_item",
                content=text,
                page_number=page_number,
                position=position,
            )

        # 5. Default Paragraph
        return ParsedElement(
            element_type="paragraph",
            content=text,
            page_number=page_number,
            position=position,
        )

    def classify_and_split_block(
        self, block: Dict[str, Any], page_number: int, position: int
    ) -> List[ParsedElement]:
        """Classifies a text block and splits it into individual elements if it is a list block."""
        text = block["text"].strip()
        is_bold = block["is_bold"]

        # Bold blocks are headings/titles and do not represent lists
        if is_bold:
            return [self.classify_text_block(block, page_number, position)]

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Determine if this text block is a list block
        is_list = False
        if lines:
            first_line = lines[0]
            if self.ORDERED_LIST_PATTERN.match(
                first_line
            ) or self.UNORDERED_LIST_PATTERN.match(first_line):
                is_list = True

        if not is_list:
            return [self.classify_text_block(block, page_number, position)]

        # It's a list block, split lines into individual items (retaining wraps)
        parsed_items: List[ParsedElement] = []
        current_type = None
        current_content = ""
        sub_pos = 0

        for line in lines:
            is_ord = self.ORDERED_LIST_PATTERN.match(line)
            is_unord = self.UNORDERED_LIST_PATTERN.match(line)

            if is_ord:
                if current_content:
                    parsed_items.append(
                        ParsedElement(
                            element_type=current_type,
                            content=current_content,
                            page_number=page_number,
                            position=position + sub_pos,
                        )
                    )
                    sub_pos += 1
                current_type = "ordered_list_item"
                current_content = line
            elif is_unord:
                if current_content:
                    parsed_items.append(
                        ParsedElement(
                            element_type=current_type,
                            content=current_content,
                            page_number=page_number,
                            position=position + sub_pos,
                        )
                    )
                    sub_pos += 1
                current_type = "unordered_list_item"
                current_content = line
            else:
                # Wrapped line continuation
                if current_content:
                    current_content += " " + line
                else:
                    current_type = "paragraph"
                    current_content = line

        if current_content:
            parsed_items.append(
                ParsedElement(
                    element_type=current_type,
                    content=current_content,
                    page_number=page_number,
                    position=position + sub_pos,
                )
            )

        return parsed_items
