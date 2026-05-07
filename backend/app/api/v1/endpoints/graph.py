"""Graph knowledge base endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_scenario_access
from app.models.graph import GraphEdge, GraphNode, GraphProject, Simulation, SimulationStep
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])


class CreateProjectRequest(BaseModel):
    organization_id: str
    name: str
    scenario_type: str = "political"
    description: str | None = None


class BuildGraphRequest(BaseModel):
    source_text: str


class PatchProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class PopulateOpinionsRequest(BaseModel):
    prompt_hint: str = ""


@router.post("", summary="Create graph project")
def create_project(
    body: CreateProjectRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = GraphService(db)
    project = svc.create_project(
        organization_id=body.organization_id,
        name=body.name,
        scenario_type=body.scenario_type,
        description=body.description,
    )
    return {
        "project_id": project.id,
        "name": project.name,
        "scenario_type": project.scenario_type,
        "status": project.status,
        "created_at": project.created_at.isoformat(),
    }


@router.get("", summary="List graph projects")
def list_projects(
    organization_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = GraphService(db)
    projects = svc.list_projects(organization_id)
    return {
        "count": len(projects),
        "items": [
            {
                "project_id": p.id,
                "name": p.name,
                "scenario_type": p.scenario_type,
                "status": p.status,
                "node_count": p.node_count,
                "edge_count": p.edge_count,
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ],
    }


@router.post("/{project_id}/build", summary="Build graph from text")
def build_graph(
    project_id: str,
    body: BuildGraphRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = GraphService(db)
    try:
        project = svc.build_graph_from_text(project_id, body.source_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {
        "project_id": project.id,
        "status": project.status,
        "node_count": project.node_count,
        "edge_count": project.edge_count,
        "description": project.description,
    }


@router.get("/{project_id}", summary="Get graph project with nodes and edges")
def get_graph(
    project_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = GraphService(db)
    try:
        return svc.get_project_graph(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{project_id}/populate-opinions", summary="Generate citizen-agent opinion nodes via AI")
def populate_opinions(
    project_id: str,
    body: PopulateOpinionsRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    svc = GraphService(db)
    try:
        return svc.populate_opinions(project_id, body.prompt_hint)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{project_id}", summary="Rename / update description of a graph project")
def patch_project(
    project_id: str,
    body: PatchProjectRequest,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    project = db.query(GraphProject).filter(GraphProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    if body.name is not None:
        project.name = body.name[:255]
    if body.description is not None:
        project.description = body.description[:500]
    db.commit()
    db.refresh(project)
    return {"project_id": project.id, "name": project.name, "description": project.description}


@router.delete("/{project_id}", summary="Delete a graph project and all its data")
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_scenario_access),
) -> dict:
    project = db.query(GraphProject).filter(GraphProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    # Cascade delete: simulation steps → simulations → edges → nodes → project
    sim_ids = [s.id for s in db.query(Simulation.id).filter(Simulation.project_id == project_id)]
    if sim_ids:
        db.query(SimulationStep).filter(SimulationStep.simulation_id.in_(sim_ids)).delete(synchronize_session=False)
        db.query(Simulation).filter(Simulation.project_id == project_id).delete(synchronize_session=False)
    db.query(GraphEdge).filter(GraphEdge.project_id == project_id).delete(synchronize_session=False)
    db.query(GraphNode).filter(GraphNode.project_id == project_id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()
    return {"deleted": project_id}
