from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampanhaProEventIngestPayload(BaseModel):
    request_id: UUID
    source_system: str = Field(default="campanhapro")
    organization_id: str
    event_type: str
    occurred_at: datetime
    payload_version: str = Field(default="1.0")
    payload: dict[str, Any] = Field(default_factory=dict)


class CampanhaProSnapshotIngestPayload(BaseModel):
    """Formato legado (v0) — sem schemaVersion. Mantido por compatibilidade."""

    request_id: UUID
    source_system: str = Field(default="campanhapro")
    organization_id: str
    snapshot_type: str
    reference_date: datetime
    payload_version: str = Field(default="1.0")
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Snapshot v1 — contrato campanhapro.snapshot.v1 (PRD v2 / Fase 1)
# ---------------------------------------------------------------------------

SNAPSHOT_V1_SCHEMA_VERSION = "campanhapro.snapshot.v1"


class SnapshotV1Actor(BaseModel):
    model_config = ConfigDict(extra="allow")
    user_id: str | None = Field(default=None, alias="userId")
    role: str | None = None


class SnapshotV1CampaignDetails(BaseModel):
    model_config = ConfigDict(extra="allow")
    nome_urna: str | None = Field(default=None, alias="nomeUrna")
    partido: str | None = None
    office: str | None = None
    municipio: str | None = None
    uf: str | None = None
    candidate_photo_url: str | None = Field(default=None, alias="candidatePhotoUrl")
    header_logo: str | None = Field(default=None, alias="headerLogo")
    footer_logo: str | None = Field(default=None, alias="footerLogo")


class SnapshotV1Campaign(BaseModel):
    model_config = ConfigDict(extra="allow")
    details: SnapshotV1CampaignDetails = Field(default_factory=SnapshotV1CampaignDetails)
    settings: dict[str, Any] = Field(default_factory=dict)
    configs: dict[str, Any] = Field(default_factory=dict)


class SnapshotV1PrivacyOptions(BaseModel):
    include_pii: bool = Field(default=False, alias="includePII")
    anonymize_names: bool = Field(default=True, alias="anonymizeNames")
    anonymize_phones: bool = Field(default=True, alias="anonymizePhones")
    anonymize_birthdates: bool = Field(default=True, alias="anonymizeBirthdates")


class SnapshotV1Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")
    records_count: int = Field(default=0, alias="recordsCount")
    window_start: datetime | None = Field(default=None, alias="windowStart")
    window_end: datetime | None = Field(default=None, alias="windowEnd")


class SnapshotV1Payload(BaseModel):
    """Snapshot oficial v1.

    Campos obrigatórios são exigidos pelo Pydantic; ausentes geram 422
    com apontamento. ``data`` aceita estrutura livre — o mapper da
    Fase 2 valida quais arrays estão presentes."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    schema_version: str = Field(alias="schemaVersion")
    snapshot_id: UUID = Field(alias="snapshotId")
    campaign_id: str = Field(alias="campaignId", min_length=1, max_length=64)
    organization_id: str = Field(alias="organizationId", min_length=1, max_length=64)
    generated_at: datetime = Field(alias="generatedAt")
    source: str | None = None
    actor: SnapshotV1Actor | None = None
    campaign: SnapshotV1Campaign = Field(default_factory=SnapshotV1Campaign)
    data: dict[str, Any] = Field(default_factory=dict)
    privacy_options: SnapshotV1PrivacyOptions = Field(
        default_factory=SnapshotV1PrivacyOptions, alias="privacyOptions"
    )
    metrics: SnapshotV1Metrics = Field(default_factory=SnapshotV1Metrics)


class IngestAcceptedResponse(BaseModel):
    status: str = "accepted"
    request_id: UUID
    detail: str
