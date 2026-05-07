from pydantic import BaseModel, Field


class AcceptancePredictionRequest(BaseModel):
    organization_id: str
    scope_type: str
    scope_id: str
    # Optional factor values (0–100 scale) for on-demand scoring.
    # When omitted the engine falls back to the latest CampanhaPro snapshot for the org.
    factors: dict[str, float] | None = Field(
        default=None,
        description="Factor scores on a 0–100 scale. Keys: training, digital_maturity, "
        "teacher_adoption, infrastructure, institutional_support, engagement.",
    )


class EvasionRiskPredictionRequest(BaseModel):
    organization_id: str
    scope_type: str
    scope_id: str
    # Optional factor values (0–100 scale) for on-demand scoring.
    factors: dict[str, float] | None = Field(
        default=None,
        description="Factor scores on a 0–100 scale. Keys: engagement, infrastructure, "
        "institutional_support, teacher_adoption.",
    )


class PredictionResponse(BaseModel):
    prediction_type: str
    organization_id: str
    scope_type: str
    scope_id: str
    value: float
    confidence: float
    explanation: list[str] = Field(default_factory=list)
