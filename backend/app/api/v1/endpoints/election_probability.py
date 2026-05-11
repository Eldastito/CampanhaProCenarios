"""Endpoints do Monte Carlo de probabilidade de eleição (Fase 4 PRD v2).

Rotas em ``/api/v1/political/projects/{project_id}/election-probability``:

- ``POST``  → cria registro queued + despacha worker. 202.
- ``GET``   → histórico (sumário).
- ``GET /{id}`` → detalhe completo.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps.auth import require_analyst
from app.models.election_probability import ElectionProbabilityResult
from app.models.political import PoliticalAuditLog, PoliticalProject
from app.models.user import User
from app.repositories.political_repository import PoliticalProjectRepository
from app.schemas.election_probability import (
    ElectionProbabilityCreate,
    ElectionProbabilityQueuedResponse,
    ElectionProbabilityResponse,
    ElectionProbabilitySummary,
)
from app.services.election_probability_service import DEFAULT_ITERATIONS
from app.workers.election_tasks import run_election_probability

router = APIRouter()


def _audit(db, *, organization_id, project_id, actor_user_id, action, target_id, payload):
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type="election_probability_result",
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


@router.post(
    "",
    response_model=ElectionProbabilityQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar simulação Monte Carlo",
)
def create_simulation(
    project_id: str,
    body: ElectionProbabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> ElectionProbabilityQueuedResponse:
    project = _load_project_or_404(db, project_id, user)

    iterations = body.iterations or DEFAULT_ITERATIONS
    row = ElectionProbabilityResult(
        id=str(uuid4()),
        organization_id=project.organization_id,
        political_project_id=project.id,
        requested_by=user.id,
        office=body.office,
        iterations=iterations,
        seed=body.seed,
        status="queued",
        input_candidates=[c.model_dump() for c in body.candidates],
        output_results=[],
        confidence_level="medium",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _audit(
        db,
        organization_id=project.organization_id,
        project_id=project.id,
        actor_user_id=user.id,
        action="election_probability.queued",
        target_id=row.id,
        payload={
            "office": body.office,
            "iterations": iterations,
            "candidates": [c.name for c in body.candidates],
            "seed": body.seed,
        },
    )

    try:
        run_election_probability.delay(row.id)
    except Exception:  # noqa: BLE001
        # Sem broker: fica queued; usuário pode disparar via re-POST.
        pass
    db.refresh(row)

    return ElectionProbabilityQueuedResponse(
        result_id=row.id,
        status=row.status,  # type: ignore[arg-type]
    )


@router.get(
    "",
    response_model=list[ElectionProbabilitySummary],
    summary="Histórico de simulações do projeto",
)
def list_simulations(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> list[ElectionProbabilitySummary]:
    project = _load_project_or_404(db, project_id, user)
    rows = (
        db.query(ElectionProbabilityResult)
        .filter(ElectionProbabilityResult.political_project_id == project.id)
        .order_by(ElectionProbabilityResult.created_at.desc())
        .all()
    )
    return [ElectionProbabilitySummary.model_validate(r) for r in rows]


@router.get(
    "/{result_id}",
    response_model=ElectionProbabilityResponse,
    summary="Detalhe de uma simulação",
)
def get_simulation(
    project_id: str,
    result_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
) -> ElectionProbabilityResponse:
    project = _load_project_or_404(db, project_id, user)
    row = (
        db.query(ElectionProbabilityResult)
        .filter(
            ElectionProbabilityResult.id == result_id,
            ElectionProbabilityResult.political_project_id == project.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Simulação não encontrada."
        )
    return ElectionProbabilityResponse.model_validate(row)
