from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class APIMessage(BaseModel):
    message: str


class TimestampedResponse(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RequestMetadata(BaseModel):
    request_id: UUID
    source_system: str
    payload_version: str = "1.0"
