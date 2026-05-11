"""Schemas Pydantic do cache de fatores CampanhaPro (Fase 2 PRD v2)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LatestFactorsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    campaign_id: str
    political_project_id: str | None
    reference_date: datetime
    factors: dict[str, float]
    coverage_percent: float
    sources_used: dict[str, list[str]]
    warnings: list[str]
    created_at: datetime
