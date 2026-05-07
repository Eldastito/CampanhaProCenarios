from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_internal_api_key
from app.schemas.predictions import (
    AcceptancePredictionRequest,
    EvasionRiskPredictionRequest,
    PredictionResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.post("/acceptance", response_model=PredictionResponse, summary="Persist acceptance prediction")
def predict_acceptance(
    body: AcceptancePredictionRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> PredictionResponse:
    value = 0.62
    confidence = 0.31
    service = PredictionService(db)
    service.save_prediction(
        organization_id=body.organization_id,
        prediction_type="acceptance",
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
    )
    return PredictionResponse(
        prediction_type="acceptance",
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
        explanation=[
            "Prediction persisted successfully.",
            "Scoring engine still uses placeholder values in this phase.",
        ],
    )


@router.post("/evasion-risk", response_model=PredictionResponse, summary="Persist evasion risk prediction")
def predict_evasion_risk(
    body: EvasionRiskPredictionRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> PredictionResponse:
    value = 0.18
    confidence = 0.27
    service = PredictionService(db)
    service.save_prediction(
        organization_id=body.organization_id,
        prediction_type="evasion-risk",
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
    )
    return PredictionResponse(
        prediction_type="evasion-risk",
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
        explanation=[
            "Prediction persisted successfully.",
            "Scoring engine still uses placeholder values in this phase.",
        ],
    )
