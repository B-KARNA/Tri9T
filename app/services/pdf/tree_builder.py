from __future__ import annotations

from typing import List

from app.services.pdf.models import ParsedDocumentNode, ParsedElement


class TreeBuilderService:
    """Builds a hierarchical document tree from a flat list of parsed elements.

    Preserves reading order and resolves parent-child relationships using heading levels.
    """

    def build_tree(self, elements: List[ParsedElement]) -> ParsedDocumentNode:
        """Constructs a tree representation from sorted parsed elements."""
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
                # Resolve parent container based on heading level depth (e.g., L=2 for 2.1)
                level = getattr(el, "level", 1)

                # Pop active headings from the stack until we find a parent heading with level < current level
                while (
                    heading_stack
                    and getattr(heading_stack[-1].element, "level", 1) >= level
                ):
                    heading_stack.pop()

                if heading_stack:
                    heading_stack[-1].add_child(node)
                else:
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
