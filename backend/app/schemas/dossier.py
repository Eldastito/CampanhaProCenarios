"""Schemas Pydantic do Dossiê de Candidato (Fase 3b PRD v2)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CandidateDossierCreate(BaseModel):
    candidate_name: str = Field(..., max_length=255)
    candidate_type: Literal["own", "opponent"]
    office: str = Field(..., max_length=100)
    party: str | None = Field(default=None, max_length=100)
    tse_candidate_id: str | None = Field(default=None, max_length=64)


class CandidateDossierQueuedResponse(BaseModel):
    """Resposta imediata do POST — pipeline ainda não rodou."""

    dossier_id: str
    status: Literal["queued", "running", "ready", "failed"]
    candidate_name: str


class CandidateDossierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    political_project_id: str
    candidate_name: str
    candidate_type: str
    party: str | None
    office: str
    tse_candidate_id: str | None

    biography: str | None
    political_history: dict[str, Any]
    current_mandates: list[Any]
    platform_and_proposals: dict[str, Any]
    legal_issues: list[Any]
    ficha_limpa_status: str | None
    recent_news: list[Any]
    media_presence: dict[str, Any]
    social_metrics: dict[str, Any]
    rejection_drivers: list[str]
    strength_drivers: list[str]
    swot: dict[str, Any]

    confidence_level: str
    sources: list[str]
    generated_by_ai: bool
    llm_models_used: list[str]
    status: str
    error_message: str | None
    last_refreshed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DossierSocialSnapshotCreate(BaseModel):
    """Entrada manual de métricas sociais para adversários (PRD v2 §3, sem APIs pagas)."""

    platform: Literal["instagram", "tiktok", "twitter", "facebook"]
    handle: str = Field(..., max_length=255)
    followers: int | None = Field(default=None, ge=0)
    posts_last_30d: int | None = Field(default=None, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0)
    avg_likes: float | None = Field(default=None, ge=0)
    avg_comments: float | None = Field(default=None, ge=0)
    notes: str | None = None


class DossierSocialSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dossier_id: str
    platform: str
    handle: str
    followers: int | None
    posts_last_30d: int | None
    engagement_rate: float | None
    avg_likes: float | None
    avg_comments: float | None
    top_posts: list[Any]
    sentiment_distribution: dict[str, Any]
    source: str
    collected_at: datetime


class CandidateDossierSummary(BaseModel):
    """Item leve para listagem."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_name: str
    candidate_type: str
    party: str | None
    office: str
    status: str
    confidence_level: str
    last_refreshed_at: datetime | None
    created_at: datetime
