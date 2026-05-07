from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.scenario_catalog import SCENARIO_CATALOG, SCENARIO_TYPE_LABELS, SCENARIO_SOURCE_SYSTEMS
from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.services.scenario_service import ScenarioService

router = APIRouter(tags=["scenarios"])


class ScenarioCreateRequest(BaseModel):
    organization_id: str
    name: str
    description: str | None = None
    scenario_type: str = "electoral"
    baseline_inputs: dict[str, Any] = Field(default_factory=dict)
    alternative_inputs: dict[str, Any] = Field(default_factory=dict)


class ScenarioRunRequest(BaseModel):
    force_recalculate: bool = False
    run_label: str | None = None


def _safe_isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.get("/catalog", summary="List available scenario types and their factors", tags=["scenarios"])
def get_scenario_catalog() -> dict:
    types = []
    for stype, factors in SCENARIO_CATALOG.items():
        types.append(
            {
                "type": stype,
                "label": SCENARIO_TYPE_LABELS.get(stype, stype),
                "source_system": SCENARIO_SOURCE_SYSTEMS.get(stype, ""),
                "factors": [
                    {"key": f.key, "label": f.label, "weight": f.weight}
                    for f in factors
                ],
            }
        )
    return {"scenario_types": types}


@router.post("", summary="Create scenario")
def create_scenario(
    body: ScenarioCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)

    try:
        scenario = service.create_scenario(
            organization_id=body.organization_id,
            name=body.name,
            description=body.description,
            scenario_type=body.scenario_type,
            baseline_inputs=body.baseline_inputs,
            alternative_inputs=body.alternative_inputs,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    response = {
        "contract_version": "v2",
        "scenario_id": scenario.id,
        "organization_id": scenario.organization_id,
        "name": scenario.name,
        "description": scenario.description,
        "status": scenario.status,
        "result_status": "fresh",
    }

    created_at = getattr(scenario, "created_at", None)
    updated_at = getattr(scenario, "updated_at", None)

    if created_at is not None:
        response["created_at"] = _safe_isoformat(created_at)

    if updated_at is not None:
        response["updated_at"] = _safe_isoformat(updated_at)

    return response


@router.get("", summary="List scenarios")
def list_scenarios(
    organization_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)
    return service.list_scenarios_view(
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )


# NOTE: /compare must be declared before /{scenario_id} to avoid route shadowing.
@router.get("/compare", summary="Compare two scenarios side by side")
def compare_scenarios(
    a: str = Query(..., description="First scenario ID"),
    b: str = Query(..., description="Second scenario ID"),
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)
    try:
        return service.compare_scenarios_view(a, b)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.post("/{scenario_id}/run", summary="Run scenario")
def run_scenario(
    scenario_id: str,
    body: ScenarioRunRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)

    try:
        execution_plan = service.get_run_execution_plan(
            scenario_id=scenario_id,
            force_recalculate=body.force_recalculate,
            run_label=body.run_label,
        )

        if not execution_plan["should_execute"]:
            results_view = service.get_results_view(scenario_id)

            return {
                "contract_version": "v2",
                "scenario_id": scenario_id,
                "execution_mode": execution_plan["execution_mode"],
                "run_created": False,
                "run_id": results_view["result_meta"]["result_source_run_id"],
                "run_status": None,
                "detail": "Fresh result reused. No new run executed.",
                "force_recalculate_received": body.force_recalculate,
                "force_recalculate_applied": False,
                "run_label": body.run_label,
                "run_decision_reason": execution_plan["reason"],
                "results": results_view,
            }

        run = service.queue_run(
            scenario_id=scenario_id,
            run_label=body.run_label,
        )

        run = service.execute_run(run.id)

        results_view = service.get_results_view(scenario_id)

        return {
            "contract_version": "v2",
            "scenario_id": scenario_id,
            "execution_mode": execution_plan["execution_mode"],
            "run_created": True,
            "run_id": run.id,
            "run_status": run.status,
            "detail": (
                "Scenario executed successfully."
                if run.status == "completed"
                else "Scenario execution finished with failure."
            ),
            "force_recalculate_received": body.force_recalculate,
            "force_recalculate_applied": body.force_recalculate,
            "run_label": body.run_label,
            "run_decision_reason": execution_plan["reason"],
            "results": results_view,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected execution error: {exc}",
        )


@router.get("/{scenario_id}/results", summary="Get scenario results")
def get_scenario_results(
    scenario_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)

    try:
        return service.get_results_view(scenario_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )


@router.get("/{scenario_id}/runs", summary="List scenario runs")
def list_scenario_runs(
    scenario_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)

    try:
        return service.list_runs_view(scenario_id=scenario_id, limit=limit)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )


@router.get("/{scenario_id}", summary="Get scenario by id")
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    service = ScenarioService(db)

    try:
        return service.get_scenario_view(scenario_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found.",
        )
