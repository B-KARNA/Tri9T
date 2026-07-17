import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.base import BaseSchema


class NodeRead(BaseSchema):
    """Schema for reading document node info."""

    id: uuid.UUID
    logical_id: uuid.UUID
    version_id: uuid.UUID
    parent_id: Optional[uuid.UUID] = None
    node_type: str
    content: str
    content_hash: str
    position: int
    created_at: datetime


class NodeChangeRead(BaseSchema):
    """Schema for reading the change history state of a node in a specific version."""

    id: uuid.UUID
    logical_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int  # Joined version number
    node_type: str
    content: str
    content_hash: str
    position: int
    created_at: datetime


class PaginatedNodes(BaseModel):
    """Paginated list wrapper for nodes."""

    items: List[NodeRead]
    total: int
    page: int
    size: int
    pages: int
