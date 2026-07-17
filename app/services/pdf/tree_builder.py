from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

from app.core.logging import logger
from app.services.pdf.models import ParsedDocumentNode, ParsedElement, ParsedHeading


class HierarchyWarning(BaseModel):
    """Represents a warning emitted when the document hierarchy is ambiguous or structurally incorrect."""

    warning_type: str  # "START_LEVEL_JUMP", "LEVEL_GAP", "ORPHAN_HEADING", "AMBIGUOUS_HEADING_LEVEL"
    message: str
    element_content: str
    page_number: int


class TreeBuilderService:
    """Builds a hierarchical document tree from a flat list of parsed elements.

    Validates hierarchy nesting and collects warnings for structural anomalies.
    """

    def __init__(self) -> None:
        self.warnings: List[HierarchyWarning] = []

    def build_tree(self, elements: List[ParsedElement]) -> ParsedDocumentNode:
        """Constructs a tree representation from sorted parsed elements, generating warnings on anomalies."""
        self.warnings = []

        # Define a virtual root node for the entire document
        virtual_root = ParsedDocumentNode(
            ParsedElement(
                element_type="document",
                content="Document Root",
                page_number=1,
                position=0,
            )
        )

        # Tracks currently active container nodes at various levels
        heading_stack: List[ParsedDocumentNode] = []

        for el in elements:
            node = ParsedDocumentNode(el)

            if el.element_type == "title":
                # Title belongs directly to the document root
                virtual_root.add_child(node)

            elif el.element_type == "heading":
                is_heading = isinstance(el, ParsedHeading)
                level = getattr(el, "level", 1)
                is_ambiguous = getattr(el, "is_ambiguous", False)

                # 1. Ambiguous heading style level warning
                if is_heading and is_ambiguous:
                    warn = HierarchyWarning(
                        warning_type="AMBIGUOUS_HEADING_LEVEL",
                        message=(
                            f"Unnumbered heading '{el.content}' styling is ambiguous. "
                            f"Inferred level {level}."
                        ),
                        element_content=el.content,
                        page_number=el.page_number,
                    )
                    self.warnings.append(warn)
                    logger.warning(
                        "Ambiguous heading level", warning=warn.model_dump()
                    )

                # 2. Document starts with nested heading warning
                if not heading_stack and level > 1:
                    warn = HierarchyWarning(
                        warning_type="START_LEVEL_JUMP",
                        message=(
                            f"Document started with nested heading '{el.content}' (level {level}) "
                            f"without a preceding level 1 heading."
                        ),
                        element_content=el.content,
                        page_number=el.page_number,
                    )
                    self.warnings.append(warn)
                    logger.warning(
                        "Nesting start level jump", warning=warn.model_dump()
                    )

                # 3. Level jump gap warning (e.g. level 1 followed directly by level 3)
                if heading_stack:
                    prev_level = getattr(
                        heading_stack[-1].element, "level", 1
                    )
                    if level > prev_level + 1:
                        warn = HierarchyWarning(
                            warning_type="LEVEL_GAP",
                            message=(
                                f"Level jump gap detected: heading '{el.content}' (level {level}) "
                                f"is nested directly under parent '{heading_stack[-1].element.content}' (level {prev_level})."
                            ),
                            element_content=el.content,
                            page_number=el.page_number,
                        )
                        self.warnings.append(warn)
                        logger.warning(
                            "Heading nesting gap", warning=warn.model_dump()
                        )

                # Resolve parent container based on heading level depth
                # Pop active headings from the stack until we find a parent heading with level < current level
                while (
                    heading_stack
                    and getattr(heading_stack[-1].element, "level", 1) >= level
                ):
                    heading_stack.pop()

                if heading_stack:
                    heading_stack[-1].add_child(node)
                else:
                    # Popped all headings, but the level is > 1.
                    # This means we must attach to root, but it is technically an orphan!
                    if level > 1:
                        warn = HierarchyWarning(
                            warning_type="ORPHAN_HEADING",
                            message=(
                                f"Orphan nested heading '{el.content}' (level {level}) "
                                f"has no available parent container; attaching to document root."
                            ),
                            element_content=el.content,
                            page_number=el.page_number,
                        )
                        self.warnings.append(warn)
                        logger.warning(
                            "Orphan nested heading", warning=warn.model_dump()
                        )
                    virtual_root.add_child(node)

                # Add current heading to the stack as the new active container
                heading_stack.append(node)

            else:
                # Paragraphs, tables, and list items belong to the active heading container,
                # or fallback to the virtual root if no heading is active yet
                if heading_stack:
                    heading_stack[-1].add_child(node)
                else:
                    virtual_root.add_child(node)

        return virtual_root
