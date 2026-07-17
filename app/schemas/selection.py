import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.base import BaseSchema


class SelectionCreate(BaseModel):
    """Schema to create a new version-pinned selection."""

    version_id: uuid.UUID
    node_ids: List[uuid.UUID]
    name: Optional[str] = None


class SelectionRead(BaseSchema):
    """Schema for reading selection info."""

    id: uuid.UUID
    document_id: uuid.UUID
    version_id: uuid.UUID
    name: Optional[str] = None
    node_ids: List[uuid.UUID]
    created_at: datetime
