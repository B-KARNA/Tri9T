from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParsedElement(BaseModel):
    """Base class for all extracted document elements."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    element_type: str  # "title", "heading", "paragraph", "ordered_list_item", "unordered_list_item", "table"
    content: str
    position: int = 0
    page_number: int


class ParsedHeading(ParsedElement):
    """Represents a section heading (e.g. 1.1 Device Overview)."""

    number_prefix: Optional[str] = None
    level: int = 1
    title: str
    is_ambiguous: bool = False


class ParsedTable(ParsedElement):
    """Represents a structured table."""

    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class ParsedDocumentNode:
    """Represents a node in the hierarchical document tree."""

    def __init__(self, element: ParsedElement):
        self.element = element
        self.children: List[ParsedDocumentNode] = []
        self.parent: Optional[ParsedDocumentNode] = None

    def add_child(self, child: ParsedDocumentNode) -> None:
        child.parent = self
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the node and its children to a dictionary."""
        res: Dict[str, Any] = {
            "type": self.element.element_type,
            "content": self.element.content,
            "page_number": self.element.page_number,
            "position": self.element.position,
        }
        if isinstance(self.element, ParsedHeading):
            res["level"] = self.element.level
            res["number_prefix"] = self.element.number_prefix
            res["title"] = self.element.title
        elif isinstance(self.element, ParsedTable):
            res["headers"] = self.element.headers
            res["rows"] = self.element.rows

        res["children"] = [c.to_dict() for c in self.children]
        return res
