"""Saved predictions endpoints."""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.time import utc_now_naive
from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.models.saved_prediction import SavedPrediction

router = APIRouter(tags=["saved-predictions"])


class SavePredictionRequest(BaseModel):
    organization_id: str
    name: str
    prediction_type: str
    scenario_type: str = "electoral"
    factors: dict
    result_value: float
    confidence: float
    explanation: list
    notes: str | None = None


@router.post("", summary="Save a prediction result", status_code=status.HTTP_201_CREATED)
def save_prediction(
    body: SavePredictionRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    record = SavedPrediction(
        id=str(uuid4()),
        organization_id=body.organization_id,
        name=body.name,
        prediction_type=body.prediction_type,
        scenario_type=body.scenario_type,
        factors=body.factors,
        result_value=body.result_value,
        confidence=body.confidence,
        explanation=body.explanation,
        notes=body.notes,
        created_at=utc_now_naive(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"saved_prediction_id": record.id, "name": record.name}


@router.get("", summary="List saved predictions")
def list_saved_predictions(
    organization_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    records = (
        db.query(SavedPrediction)
        .filter(SavedPrediction.organization_id == organization_id)
        .order_by(SavedPrediction.created_at.desc())
        .all()
    )
    return {
        "count": len(records),
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "prediction_type": r.prediction_type,
                "scenario_type": r.scenario_type,
                "result_value": r.result_value,
                "confidence": r.confidence,
                "factors": r.factors,
                "explanation": r.explanation,
                "notes": r.notes,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }


@router.delete("/{prediction_id}", summary="Delete saved prediction")
def delete_saved_prediction(
    prediction_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    record = db.query(SavedPrediction).filter(SavedPrediction.id == prediction_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    db.delete(record)
    db.commit()
    return {"deleted": True}
