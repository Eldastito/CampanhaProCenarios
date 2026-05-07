"""Schemas Pydantic do domínio político-eleitoral."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# PoliticalProject
# ---------------------------------------------------------------------------


class PoliticalProjectBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    election_year: int = Field(..., ge=2020, le=2100)
    office: str = Field(..., max_length=100)
    state: str | None = Field(default=None, max_length=2)
    municipality: str | None = Field(default=None, max_length=255)
    candidate_name: str = Field(..., max_length=255)
    parties: list[str] = Field(default_factory=list)
    known_opponents: list[str] = Field(default_factory=list)
    objective: str | None = None
    horizon_start: datetime | None = None
    horizon_end: datetime | None = None


class PoliticalProjectCreate(PoliticalProjectBase):
    organization_id: str = Field(..., max_length=64)


class PoliticalProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    state: str | None = Field(default=None, max_length=2)
    municipality: str | None = Field(default=None, max_length=255)
    parties: list[str] | None = None
    known_opponents: list[str] | None = None
    objective: str | None = None
    horizon_start: datetime | None = None
    horizon_end: datetime | None = None
    status: str | None = Field(default=None, max_length=32)


class PoliticalProjectResponse(PoliticalProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# PoliticalEvidenceSource — Fase 2: ingestão e listagem
# ---------------------------------------------------------------------------


class PoliticalEvidenceManualCreate(BaseModel):
    """Cadastro de evidência via texto/link, sem upload de arquivo binário."""

    title: str = Field(..., max_length=500)
    source_type: str = Field(..., description="manual | link | txt | md")
    raw_text: str | None = Field(default=None, description="Texto cru quando source_type='manual'.")
    source_name: str | None = Field(default=None, max_length=255)
    source_url: str | None = Field(default=None, max_length=1000)
    author: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None
    reliability_override: str | None = Field(
        default=None,
        description=(
            "Força um nível de confiabilidade (oficial/press/registered_poll/"
            "public_base/internal/social/unverified). Se omitido, o serviço infere."
        ),
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class PoliticalEvidenceSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    project_id: str
    title: str
    source_type: str
    source_name: str | None
    source_url: str | None
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    reliability_level: str
    content_hash: str | None
    storage_uri: str | None
    metadata_json: dict[str, Any]
    processing_status: str
    processing_error: str | None
    created_by: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# PoliticalComplianceAlert
# ---------------------------------------------------------------------------


class PoliticalComplianceAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    project_id: str | None
    alert_type: str
    severity: str
    message: str
    related_entity_type: str | None
    related_entity_id: str | None
    context: dict[str, Any]
    status: str
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime
