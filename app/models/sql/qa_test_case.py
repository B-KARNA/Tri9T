from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List

from sqlalchemy import DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.sql.document import DocumentVersion
from app.models.sql.selection import Selection


class GeneratedTestCase(Base):
    """Represents a QA test case generated from a selection highlight.

    Retains immutable references to the version, node IDs, and content hashes
    it was originally derived from to enable stale traceability.
    """

    __tablename__ = "generated_test_cases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("selections.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # JSON lists/dicts representing nodes and hashes at the time of generation
    referenced_node_ids: Mapped[List[str]] = mapped_column(
        JSON, nullable=False
    )  # List of UUID strings
    referenced_content_hashes: Mapped[Dict[str, str]] = mapped_column(
        JSON, nullable=False
    )  # Map of node_id_str -> content_hash_str

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    selection: Mapped[Selection] = relationship(lazy="selectin")
    version: Mapped[DocumentVersion] = relationship(lazy="selectin")
