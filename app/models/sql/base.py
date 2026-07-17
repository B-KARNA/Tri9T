# Import all models here so that Alembic can detect them via metadata
from app.core.database import Base  # noqa
from app.models.sql.document import Document, DocumentVersion  # noqa
from app.models.sql.llm_failure import LLMFailureLog  # noqa
from app.models.sql.node import Node  # noqa
from app.models.sql.selection import Selection, SelectionNodeMapping  # noqa

__all__ = [
    "Base",
    "Document",
    "DocumentVersion",
    "LLMFailureLog",
    "Node",
    "Selection",
    "SelectionNodeMapping",
]
