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


class QATestCase(BaseModel):
    """Represents a single generated Question and Answer test case."""

    question: str
    answer: str


class QATestCaseList(BaseModel):
    """Wrapper containing a list of generated QA test cases."""

    test_cases: List[QATestCase]


class LLMFailureLogRead(BaseSchema):
    """Schema for reading logged LLM validation or API failures."""

    id: uuid.UUID
    selection_id: uuid.UUID
    error_message: str
    raw_response: Optional[str] = None
    created_at: datetime


class QATestCaseTrace(BaseModel):
    """Represents the traceability validation state of a generated test case."""

    test_case_id: uuid.UUID
    question: str
    status: str  # "Fresh", "Possibly stale", "Stale"
    reason: str


class QATraceabilityResponse(BaseModel):
    """Contains the overall traceability validation report for a selection's QA test cases."""

    selection_id: uuid.UUID
    target_version_id: uuid.UUID
    results: List[QATestCaseTrace]


class VersionInfo(BaseModel):
    """Metadata representing a specific document version."""

    id: uuid.UUID
    version_number: int
    commit_message: Optional[str] = None
    created_at: datetime


class QAWithTraceability(BaseModel):
    """Represents a generated test case enriched with traceability status and text diffs."""

    id: uuid.UUID
    question: str
    answer: str
    status: str  # "Fresh", "Possibly stale", "Stale"
    reason: str
    diff_summary: str


class GenerationRetrievalResponse(BaseModel):
    """Full generation report for a selection or node query."""

    selection_id: Optional[uuid.UUID] = None
    original_version: VersionInfo
    current_version: VersionInfo
    staleness_status: str  # Overall status: "Fresh", "Possibly stale", or "Stale"
    test_cases: List[QAWithTraceability]

