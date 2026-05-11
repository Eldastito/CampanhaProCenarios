"""Endpoints de projetos eleitorais (Fase 1 — CRUD básico).

Um projeto agrupa cenários, evidências, agentes e simulações de uma
campanha específica.  Authn por JWT (analista do tenant).  Cada operação é
registrada em ``political_audit_logs`` para trilha de compliance.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.political import PoliticalAuditLog, PoliticalProject
from app.models.user import User
from app.repositories.factor_cache_repository import CampanhaProFactorCacheRepository
from app.repositories.political_repository import (
    PoliticalAuditLogRepository,
    PoliticalProjectRepository,
)
from app.schemas.factor_cache import LatestFactorsResponse
from app.schemas.political import (
    PoliticalProjectCreate,
    PoliticalProjectResponse,
    PoliticalProjectUpdate,
)

router = APIRouter()


# Limite MVP definido no PRD v2 §4: cada organização pode manter no máximo
# 10 campanhas simultâneas (DISTINCT campaign_id). Múltiplos projetos da
# mesma campanha não consomem slots adicionais.
MVP_CAMPAIGN_LIMIT_PER_ORG = 10


def _audit(
    db: Session,
    *,
    organization_id: str,
    project_id: str | None,
    actor_user_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict | None = None,
) -> None:
    PoliticalAuditLogRepository(db).add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            payload=payload or {},
        )
    )


def _ensure_same_org(project: PoliticalProject, user: User) -> None:
    if project.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projeto não encontrado.",
        )


@router.post(
    "",
    response_model=PoliticalProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar projeto eleitoral",
)
def create_project(
    body: PoliticalProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalProjectResponse:
    if body.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="organization_id não corresponde à organização do usuário.",
        )

    repo = PoliticalProjectRepository(db)

    # Quota MVP: bloqueia se a organização já atingiu o limite e o
    # campaign_id solicitado é uma campanha nova. Reuso de campaign_id
    # existente (criar um segundo projeto na mesma campanha) é permitido.
    project_id = str(uuid4())
    campaign_id = body.campaign_id or project_id
    is_new_campaign = not repo.has_campaign(body.organization_id, campaign_id)
    if is_new_campaign:
        active = repo.count_distinct_campaigns(body.organization_id)
        if active >= MVP_CAMPAIGN_LIMIT_PER_ORG:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Limite MVP de {MVP_CAMPAIGN_LIMIT_PER_ORG} campanhas "
                    "simultâneas atingido para esta organização."
                ),
            )

    project = PoliticalProject(
        id=project_id,
        organization_id=body.organization_id,
        campaign_id=campaign_id,
        name=body.name,
        description=body.description,
        election_year=body.election_year,
        office=body.office,
        state=body.state,
        municipality=body.municipality,
        candidate_name=body.candidate_name,
        parties=body.parties,
        known_opponents=body.known_opponents,
        objective=body.objective,
        horizon_start=body.horizon_start,
        horizon_end=body.horizon_end,
        status="draft",
        created_by=user.id,
    )
    saved = repo.add(project)

    _audit(
        db,
        organization_id=saved.organization_id,
        project_id=saved.id,
        actor_user_id=user.id,
        action="political_project.created",
        target_type="political_project",
        target_id=saved.id,
        payload={
            "name": saved.name,
            "office": saved.office,
            "year": saved.election_year,
            "campaign_id": saved.campaign_id,
            "new_campaign": is_new_campaign,
        },
    )

    return PoliticalProjectResponse.model_validate(saved)


@router.get(
    "",
    response_model=list[PoliticalProjectResponse],
    summary="Listar projetos eleitorais da organização",
)
def list_projects(
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PoliticalProjectResponse]:
    repo = PoliticalProjectRepository(db)
    projects = repo.list_for_org(user.organization_id, limit=limit, offset=offset)
    return [PoliticalProjectResponse.model_validate(p) for p in projects]


@router.get(
    "/{project_id}",
    response_model=PoliticalProjectResponse,
    summary="Obter projeto eleitoral por id",
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalProjectResponse:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    _ensure_same_org(project, user)
    return PoliticalProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=PoliticalProjectResponse,
    summary="Atualizar projeto eleitoral",
)
def update_project(
    project_id: str,
    body: PoliticalProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> PoliticalProjectResponse:
    repo = PoliticalProjectRepository(db)
    project = repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    _ensure_same_org(project, user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    saved = repo.update(project)

    _audit(
        db,
        organization_id=saved.organization_id,
        project_id=saved.id,
        actor_user_id=user.id,
        action="political_project.updated",
        target_type="political_project",
        target_id=saved.id,
        payload={"fields": list(update_data.keys())},
    )

    return PoliticalProjectResponse.model_validate(saved)


@router.get(
    "/{project_id}/latest-factors",
    response_model=LatestFactorsResponse,
    summary="Último cache de fatores derivado de snapshot CampanhaPro v1",
)
def get_latest_factors(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> LatestFactorsResponse:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    _ensure_same_org(project, user)

    cache_repo = CampanhaProFactorCacheRepository(db)
    # Tenta primeiro pelo project_id (FK direta); cai pra campaign_id
    # quando o mapper rodou antes do projeto existir / sem FK setada.
    cache = cache_repo.latest_for_project(user.organization_id, project.id)
    if cache is None:
        cache = cache_repo.latest_for_campaign(user.organization_id, project.campaign_id)

    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum snapshot CampanhaPro v1 processado para esta campanha ainda.",
        )

    return LatestFactorsResponse.model_validate(cache)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Excluir projeto eleitoral (somente admin)",
)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> Response:
    repo = PoliticalProjectRepository(db)
    project = repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    _ensure_same_org(project, user)

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem excluir projetos.",
        )

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=None,
        actor_user_id=user.id,
        action="political_project.deleted",
        target_type="political_project",
        target_id=project.id,
        payload={"name": project.name},
    )
    repo.delete(project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
