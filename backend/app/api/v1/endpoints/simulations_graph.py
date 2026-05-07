"""Simulation endpoints."""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.services.simulation_service import SimulationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["simulations"])


class CreateSimulationRequest(BaseModel):
    project_id: str
    organization_id: str
    name: str
    prompt: str | None = None


class RunSimulationRequest(BaseModel):
    num_steps: int = 12


@router.post("", summary="Create simulation")
def create_simulation(
    body: CreateSimulationRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = SimulationService(db)
    sim = svc.create_simulation(
        project_id=body.project_id,
        organization_id=body.organization_id,
        name=body.name,
        prompt=body.prompt,
    )
    return {
        "simulation_id": sim.id,
        "name": sim.name,
        "status": sim.status,
        "created_at": sim.created_at.isoformat(),
    }


@router.post("/{simulation_id}/run", summary="Run simulation (generates all steps)")
def run_simulation(
    simulation_id: str,
    body: RunSimulationRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = SimulationService(db)
    try:
        sim = svc.run_simulation(simulation_id, num_steps=body.num_steps)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {
        "simulation_id": sim.id,
        "status": sim.status,
        "summary": sim.summary,
        "step_count": sim.step_count,
    }


@router.post("/{simulation_id}/stream-run", summary="Run simulation and stream steps via SSE")
async def stream_run_simulation(
    simulation_id: str,
    body: RunSimulationRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> StreamingResponse:
    svc = SimulationService(db)

    async def generate():
        try:
            loop = asyncio.get_event_loop()
            enriched_steps, summary = await loop.run_in_executor(
                None,
                lambda: svc.prepare_streaming_steps(simulation_id, body.num_steps),
            )
            for step in enriched_steps:
                payload = {"type": "step", **step}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.38)

            done_payload = {
                "type": "done",
                "summary": summary,
                "step_count": len(enriched_steps),
            }
            yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("stream_run_error", extra={"error": str(exc)})
            error_payload = {"type": "error", "message": str(exc)}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("", summary="List simulations")
def list_simulations(
    organization_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = SimulationService(db)
    sims = svc.list_simulations(organization_id)
    return {
        "count": len(sims),
        "items": [
            {
                "simulation_id": s.id,
                "project_id": s.project_id,
                "name": s.name,
                "status": s.status,
                "step_count": s.step_count,
                "created_at": s.created_at.isoformat(),
            }
            for s in sims
        ],
    }


@router.get("/{simulation_id}", summary="Get simulation with all steps")
def get_simulation(
    simulation_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = SimulationService(db)
    try:
        return svc.get_simulation_view(simulation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
