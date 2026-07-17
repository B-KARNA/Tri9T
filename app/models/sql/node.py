from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sql.document import DocumentVersion
    from app.models.sql.selection import SelectionNodeMapping


class Node(Base):
    """Represents a structural block or content node within a specific document version."""

    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Stable identifier of this logical node across multiple document versions
    logical_id: Mapped[uuid.UUID] = mapped_column(
        default=uuid.uuid4, nullable=False
    )

    # Version scope
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )

    # Self-referential hierarchy
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True
    )

    node_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Content hashing for change detection and diffing
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Sibling ordering under the same parent
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Indexes
    __table_args__ = (
        Index("ix_nodes_version_logical", "version_id", "logical_id"),
        Index(
            "ix_nodes_version_parent_pos",
            "version_id",
            "parent_id",
            "position",
        ),
        Index("ix_nodes_content_hash", "content_hash"),
    )

    # Relationships
    version: Mapped[DocumentVersion] = relationship(
        back_populates="nodes", lazy="selectin"
    )

    # Self-referential parent-child relationships
    parent: Mapped[Optional[Node]] = relationship(
        remote_side="[Node.id]", back_populates="children", lazy="selectin"
    )
    children: Mapped[List[Node]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Node.position",
        lazy="selectin",
    )

    # Mappings to user selections
    selection_mappings: Mapped[List[SelectionNodeMapping]] = relationship(
        back_populates="node", cascade="all, delete-orphan", lazy="selectin"
    )
