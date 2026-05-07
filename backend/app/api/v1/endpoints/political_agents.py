"""Endpoints de bancada de agentes políticos (Fase 4)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.user import User
from app.repositories.political_repository import (
    PoliticalAgentRepository,
    PoliticalProjectRepository,
)
from app.schemas.political import (
    PoliticalAgentProfileResponse,
    PoliticalAgentSeedResult,
)
from app.services.political_agent_service import PoliticalAgentService

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_project(project_id: str, db: Session, user: User):
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    return project


@router.post(
    "/projects/{project_id}/agents/seed-specialists",
    response_model=PoliticalAgentSeedResult,
    summary="Semear bancada de especialistas fixos para o projeto",
)
def seed_specialists(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalAgentSeedResult:
    project = _ensure_project(project_id, db, user)
    service = PoliticalAgentService(db)
    created, skipped = service.seed_fixed_specialists(project=project, actor_user_id=user.id)
    detail = (
        f"{created} especialistas criados, {skipped} já existiam."
        if created
        else "Bancada de especialistas já estava completa."
    )
    return PoliticalAgentSeedResult(
        project_id=project_id,
        created_count=created,
        skipped_count=skipped,
        detail=detail,
    )


@router.post(
    "/projects/{project_id}/agents/generate-from-graph",
    response_model=PoliticalAgentSeedResult,
    summary="Gerar agentes a partir do grafo político do projeto",
)
def generate_from_graph(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalAgentSeedResult:
    project = _ensure_project(project_id, db, user)
    service = PoliticalAgentService(db)
    try:
        created, removed_old = service.generate_from_graph(
            project=project, actor_user_id=user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PoliticalAgentSeedResult(
        project_id=project_id,
        created_count=created,
        skipped_count=removed_old,  # reusa o campo: aqui significa "removed_previous"
        detail=(
            f"{created} agentes gerados a partir do grafo. "
            f"{removed_old} agentes gerados anteriormente foram substituídos."
        ),
    )


@router.get(
    "/projects/{project_id}/agents",
    response_model=list[PoliticalAgentProfileResponse],
    summary="Listar bancada de agentes do projeto",
)
def list_agents(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
    agent_type: str | None = Query(default=None, description="fixed_specialist | generated"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PoliticalAgentProfileResponse]:
    project = _ensure_project(project_id, db, user)
    items = PoliticalAgentRepository(db).list_for_project(
        project.id, agent_type=agent_type, limit=limit, offset=offset
    )
    return [PoliticalAgentProfileResponse.model_validate(a) for a in items]


@router.get(
    "/agents/{agent_id}",
    response_model=PoliticalAgentProfileResponse,
    summary="Obter detalhe de um agente",
)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalAgentProfileResponse:
    record = PoliticalAgentRepository(db).get_by_id(agent_id)
    if record is None or record.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado.")
    return PoliticalAgentProfileResponse.model_validate(record)
