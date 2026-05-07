from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.schemas.predictions import (
    AcceptancePredictionRequest,
    EvasionRiskPredictionRequest,
    PredictionResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter()


@router.post("/acceptance", response_model=PredictionResponse, summary="Estimate CampanhaPro acceptance")
def predict_acceptance(
    body: AcceptancePredictionRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> PredictionResponse:
    service = PredictionService(db)
    value, confidence, explanation = service.predict_acceptance(
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        factors=body.factors,
    )
    return PredictionResponse(
        prediction_type="acceptance",
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
        explanation=explanation,
    )


@router.post("/evasion-risk", response_model=PredictionResponse, summary="Estimate evasion risk")
def predict_evasion_risk(
    body: EvasionRiskPredictionRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> PredictionResponse:
    service = PredictionService(db)
    value, confidence, explanation = service.predict_evasion_risk(
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        factors=body.factors,
    )
    return PredictionResponse(
        prediction_type="evasion-risk",
        organization_id=body.organization_id,
        scope_type=body.scope_type,
        scope_id=body.scope_id,
        value=value,
        confidence=confidence,
        explanation=explanation,
    )
