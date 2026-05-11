"""Schemas Pydantic do Monte Carlo de probabilidade de eleição (Fase 4)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ElectionCandidateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    factors: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ElectionProbabilityCreate(BaseModel):
    office: str = Field(..., max_length=100)
    candidates: list[ElectionCandidateInput] = Field(..., min_length=2, max_length=10)
    iterations: int | None = Field(default=None, ge=100, le=50_000)
    seed: int | None = None
    two_rounds: bool | None = Field(
        default=None,
        description="Força 2 turnos. Quando None, infere por office.",
    )


class ElectionProbabilityQueuedResponse(BaseModel):
    result_id: str
    status: Literal["queued", "running", "completed", "failed"]


class ElectionResultItem(BaseModel):
    candidate_name: str
    win_probability: float
    win_first_round_probability: float
    mean_share_first_round: float
    share_ci_95_first_round: list[float]
    second_round_qualification_probability: float | None
    second_round_win_given_qualified: float | None
    input_confidence: float


class ElectionProbabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    political_project_id: str
    requested_by: str | None
    office: str
    iterations: int
    seed: int | None
    status: str
    error_message: str | None
    input_candidates: list[dict[str, Any]]
    output_results: list[ElectionResultItem]
    confidence_level: str
    created_at: datetime
    completed_at: datetime | None


class ElectionProbabilitySummary(BaseModel):
    """Item leve para histórico."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    office: str
    iterations: int
    status: str
    confidence_level: str
    created_at: datetime
    completed_at: datetime | None
