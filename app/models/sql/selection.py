from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sql.document import Document, DocumentVersion
    from app.models.sql.node import Node


class Selection(Base):
    """Represents a user-defined selection pinned to a specific document version."""

    __tablename__ = "selections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    document: Mapped[Document] = relationship(lazy="selectin")
    version: Mapped[DocumentVersion] = relationship(
        back_populates="selections", lazy="selectin"
    )
    node_mappings: Mapped[List[SelectionNodeMapping]] = relationship(
        back_populates="selection", cascade="all, delete-orphan", lazy="selectin"
    )


class SelectionNodeMapping(Base):
    """Connects a Selection highlight to specific structural Nodes in the tree."""

    __tablename__ = "selection_node_mappings"

    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("selections.id", ondelete="CASCADE"), primary_key=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True
    )

    # Optional character-level offsets within the node's content
    anchor_offset: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    focus_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    selection: Mapped[Selection] = relationship(
        back_populates="node_mappings", lazy="selectin"
    )
    node: Mapped[Node] = relationship(
        back_populates="selection_mappings", lazy="selectin"
    )
