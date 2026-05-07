from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CampanhaProEventIngestPayload(BaseModel):
    request_id: UUID
    source_system: str = Field(default="campanhapro")
    organization_id: str
    event_type: str
    occurred_at: datetime
    payload_version: str = Field(default="1.0")
    payload: dict[str, Any] = Field(default_factory=dict)


class CampanhaProSnapshotIngestPayload(BaseModel):
    request_id: UUID
    source_system: str = Field(default="campanhapro")
    organization_id: str
    snapshot_type: str
    reference_date: datetime
    payload_version: str = Field(default="1.0")
    payload: dict[str, Any] = Field(default_factory=dict)


class IngestAcceptedResponse(BaseModel):
    status: str = "accepted"
    request_id: UUID
    detail: str
