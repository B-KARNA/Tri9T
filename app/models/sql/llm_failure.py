from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LLMFailureLog(Base):
    """Stores logs of LLM validation or API failures for auditing and retry tracking."""

    __tablename__ = "llm_failure_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    selection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("selections.id", ondelete="CASCADE"), nullable=False
    )
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    selection: Mapped[Selection] = relationship(lazy="selectin")
