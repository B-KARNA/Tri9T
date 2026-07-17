import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.base import BaseSchema


class DocumentRead(BaseSchema):
    """Schema for reading document info."""

    id: uuid.UUID
    name: str
    created_at: datetime


class DocumentVersionRead(BaseSchema):
    """Schema for reading document version info."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    commit_message: Optional[str] = None
    created_at: datetime


class PaginatedDocuments(BaseModel):
    """Paginated list wrapper for documents."""

    items: List[DocumentRead]
    total: int
    page: int
    size: int
    pages: int


class PaginatedDocumentVersions(BaseModel):
    """Paginated list wrapper for document versions."""

    items: List[DocumentVersionRead]
    total: int
    page: int
    size: int
    pages: int
