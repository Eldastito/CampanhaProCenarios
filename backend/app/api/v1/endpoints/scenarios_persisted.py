from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_internal_api_key
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_service import ScenarioService

router = APIRouter()


class ScenarioCreateRequest(BaseModel):
    organization_id: str
    name: str
    description: str | None = None
    baseline_inputs: dict = Field(default_factory=dict)
    alternative_inputs: dict = Field(default_factory=dict)


class ScenarioRunRequest(BaseModel):
    run_label: str | None = None
    force_recalculate: bool = False


@router.post("", summary="Create persisted scenario")
def create_scenario(
    body: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> dict:
    service = ScenarioService(db)
    scenario = service.create_scenario(
        organization_id=body.organization_id,
        name=body.name,
        description=body.description,
    )
    return {
        "scenario_id": scenario.id,
        "organization_id": scenario.organization_id,
        "name": scenario.name,
        "description": scenario.description,
        "status": scenario.status,
    }


@router.post("/{scenario_id}/run", summary="Queue persisted scenario run")
def run_scenario(
    scenario_id: str,
    body: ScenarioRunRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> dict:
    repository = ScenarioRepository(db)
    scenario = repository.get_by_id(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )

    service = ScenarioService(db)
    run = service.queue_run(scenario_id=scenario_id)
    return {
        "scenario_id": scenario_id,
        "run_id": run.id,
        "status": run.status,
        "detail": "Scenario execution queued for processing.",
        "force_recalculate": body.force_recalculate,
        "run_label": body.run_label,
    }


@router.get("/{scenario_id}/results", summary="Get persisted scenario result placeholder")
def get_scenario_results(
    scenario_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_api_key),
) -> dict:
    repository = ScenarioRepository(db)
    scenario = repository.get_by_id(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )

    return {
        "scenario_id": scenario.id,
        "status": scenario.status,
        "result": {
            "baseline_score": 0.58,
            "alternative_score": 0.71,
            "delta": 0.13,
            "detail": "Persisted scenario found. Result engine still placeholder.",
        },
    }
