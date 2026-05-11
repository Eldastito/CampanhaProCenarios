"""Endpoints do Dossiê de Candidato (Fase 3b PRD v2).

Rotas montadas em ``/api/v1/political/projects/{project_id}/dossiers``:

- ``POST``  → cria dossiê (status=queued) + despacha worker Celery.
- ``GET``   → lista dossiês do projeto (sumário).
- ``GET /{dossier_id}`` → dossiê completo.
- ``POST /{dossier_id}/refresh`` → re-roda pipeline.
- ``DELETE /{dossier_id}`` → remove dossiê (admin).
- ``POST /{dossier_id}/social-snapshots`` → entrada manual de métricas
  sociais (para adversários sem API).
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.dossier import CandidateDossier, DossierSocialSnapshot
from app.models.political import PoliticalAuditLog, PoliticalProject
from app.models.user import User
from app.repositories.political_repository import PoliticalProjectRepository
from app.schemas.dossier import (
    CandidateDossierCreate,
    CandidateDossierQueuedResponse,
    CandidateDossierResponse,
    CandidateDossierSummary,
    DossierSocialSnapshotCreate,
    DossierSocialSnapshotResponse,
)
from app.workers.dossier_tasks import generate_dossier_task

router = APIRouter()


def _audit(
    db: Session,
    *,
    organization_id: str,
    project_id: str,
    actor_user_id: str | None,
    action: str,
    target_id: str,
    payload: dict,
) -> None:
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="candidate_dossier",
            target_id=target_id,
            payload=payload,
        )
    )
    db.commit()


def _load_project_or_404(db: Session, project_id: str, user: User) -> PoliticalProject:
    project = PoliticalProjectRepository(db).get_by_id(project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado.")
    return project


def _load_dossier_or_404(
    db: Session, project: PoliticalProject, dossier_id: str
) -> CandidateDossier:
    dossier = (
        db.query(CandidateDossier)
        .filter(
            CandidateDossier.id == dossier_id,
            CandidateDossier.political_project_id == project.id,
        )
        .first()
    )
    if dossier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossiê não encontrado.")
    return dossier


def _dispatch_pipeline(dossier_id: str) -> None:
    try:
        generate_dossier_task.delay(dossier_id)
    except Exception:  # noqa: BLE001
        # Broker indisponível: dossiê fica em queued, pode ser disparado
        # manualmente via refresh quando worker voltar.
        pass


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=CandidateDossierQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Criar dossiê e disparar pipeline",
)
def create_dossier(
    project_id: str,
    body: CandidateDossierCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> CandidateDossierQueuedResponse:
    project = _load_project_or_404(db, project_id, user)

    dossier = CandidateDossier(
        id=str(uuid4()),
        organization_id=project.organization_id,
        political_project_id=project.id,
        candidate_name=body.candidate_name,
        candidate_type=body.candidate_type,
        party=body.party,
        office=body.office,
        tse_candidate_id=body.tse_candidate_id,
        status="queued",
    )
    db.add(dossier)
    db.commit()
    db.refresh(dossier)

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="dossier.queued",
        target_id=dossier.id,
        payload={
            "candidate_name": dossier.candidate_name,
            "candidate_type": dossier.candidate_type,
        },
    )

    _dispatch_pipeline(dossier.id)
    db.refresh(dossier)

    return CandidateDossierQueuedResponse(
        dossier_id=dossier.id,
        status=dossier.status,  # type: ignore[arg-type]
        candidate_name=dossier.candidate_name,
    )


@router.get(
    "",
    response_model=list[CandidateDossierSummary],
    summary="Listar dossiês do projeto",
)
def list_dossiers(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> list[CandidateDossierSummary]:
    project = _load_project_or_404(db, project_id, user)
    rows = (
        db.query(CandidateDossier)
        .filter(CandidateDossier.political_project_id == project.id)
        .order_by(CandidateDossier.created_at.desc())
        .all()
    )
    return [CandidateDossierSummary.model_validate(r) for r in rows]


@router.get(
    "/{dossier_id}",
    response_model=CandidateDossierResponse,
    summary="Dossiê completo",
)
def get_dossier(
    project_id: str,
    dossier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> CandidateDossierResponse:
    project = _load_project_or_404(db, project_id, user)
    dossier = _load_dossier_or_404(db, project, dossier_id)
    return CandidateDossierResponse.model_validate(dossier)


@router.post(
    "/{dossier_id}/refresh",
    response_model=CandidateDossierQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-roda o pipeline de geração",
)
def refresh_dossier(
    project_id: str,
    dossier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> CandidateDossierQueuedResponse:
    project = _load_project_or_404(db, project_id, user)
    dossier = _load_dossier_or_404(db, project, dossier_id)

    dossier.status = "queued"
    dossier.error_message = None
    db.commit()
    db.refresh(dossier)

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="dossier.refresh_requested",
        target_id=dossier.id,
        payload={"candidate_name": dossier.candidate_name},
    )

    _dispatch_pipeline(dossier.id)
    db.refresh(dossier)

    return CandidateDossierQueuedResponse(
        dossier_id=dossier.id,
        status=dossier.status,  # type: ignore[arg-type]
        candidate_name=dossier.candidate_name,
    )


@router.delete(
    "/{dossier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Remover dossiê",
)
def delete_dossier(
    project_id: str,
    dossier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> Response:
    project = _load_project_or_404(db, project_id, user)
    dossier = _load_dossier_or_404(db, project, dossier_id)
    candidate_name = dossier.candidate_name
    db.delete(dossier)
    db.commit()
    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="dossier.deleted",
        target_id=dossier_id,
        payload={"candidate_name": candidate_name},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Social snapshots manuais (Twitter/TikTok adversários sem API)
# ---------------------------------------------------------------------------


@router.post(
    "/{dossier_id}/social-snapshots",
    response_model=DossierSocialSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Entrada manual de métricas sociais (adversários)",
)
def add_social_snapshot(
    project_id: str,
    dossier_id: str,
    body: DossierSocialSnapshotCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> DossierSocialSnapshotResponse:
    project = _load_project_or_404(db, project_id, user)
    dossier = _load_dossier_or_404(db, project, dossier_id)

    snapshot = DossierSocialSnapshot(
        id=str(uuid4()),
        dossier_id=dossier.id,
        platform=body.platform,
        handle=body.handle,
        followers=body.followers,
        posts_last_30d=body.posts_last_30d,
        engagement_rate=body.engagement_rate,
        avg_likes=body.avg_likes,
        avg_comments=body.avg_comments,
        source="manual",
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="dossier.social_snapshot_added",
        target_id=dossier.id,
        payload={
            "platform": body.platform,
            "handle": body.handle,
            "source": "manual",
        },
    )
    return DossierSocialSnapshotResponse.model_validate(snapshot)


@router.get(
    "/{dossier_id}/social-snapshots",
    response_model=list[DossierSocialSnapshotResponse],
    summary="Lista snapshots sociais do dossiê",
)
def list_social_snapshots(
    project_id: str,
    dossier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> list[DossierSocialSnapshotResponse]:
    project = _load_project_or_404(db, project_id, user)
    dossier = _load_dossier_or_404(db, project, dossier_id)
    rows = (
        db.query(DossierSocialSnapshot)
        .filter(DossierSocialSnapshot.dossier_id == dossier.id)
        .order_by(DossierSocialSnapshot.collected_at.desc())
        .all()
    )
    return [DossierSocialSnapshotResponse.model_validate(r) for r in rows]
