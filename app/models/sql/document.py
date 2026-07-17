from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sql.node import Node
    from app.models.sql.selection import Selection


class Document(Base):
    """Represents a root-level document in the system."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    versions: Mapped[List[DocumentVersion]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number",
        lazy="selectin",
    )


class DocumentVersion(Base):
    """Represents a specific revision of a document."""

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "document_id", "version_number", name="uq_document_version_number"
        ),
    )

    # Relationships
    document: Mapped[Document] = relationship(
        back_populates="versions", lazy="selectin"
    )
    nodes: Mapped[List[Node]] = relationship(
        back_populates="version", cascade="all, delete-orphan", lazy="selectin"
    )
    selections: Mapped[List[Selection]] = relationship(
        back_populates="version", cascade="all, delete-orphan", lazy="selectin"
    )
