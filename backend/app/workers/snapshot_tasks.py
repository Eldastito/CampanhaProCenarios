"""Celery tasks que processam snapshots CampanhaPro v1 (Fase 2 PRD v2).

A task ``process_snapshot_factors`` é despachada pelo endpoint de ingest
após persistir o snapshot. Roda fora do request — em produção via worker
dedicado, em testes via ``task_always_eager`` (síncrono).

Idempotente: se já existe um cache para o snapshot, faz no-op.

Atualiza branding (header_logo_url, footer_logo_url, candidate_photo_url)
nos ``political_projects`` da campanha quando ainda não estiverem definidos.
Isso prepara terreno para a Fase 5 (relatórios com branding).
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.campanhapro_ingest import CampanhaProSnapshot
from app.models.dossier import CandidateDossier, DossierSocialSnapshot
from app.models.factor_cache import CampanhaProFactorCache
from app.models.political import PoliticalAuditLog, PoliticalProject
from app.repositories.factor_cache_repository import CampanhaProFactorCacheRepository
from app.services.campanhapro_factor_mapper import map_snapshot_to_factors
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _audit(
    db: Session,
    *,
    organization_id: str,
    project_id: str | None,
    action: str,
    payload: dict,
) -> None:
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=None,
            action=action,
            target_type="campanhapro_snapshot",
            target_id=payload.get("snapshot_id"),
            payload=payload,
        )
    )
    db.commit()


def _own_dossier_context(db: Session, snapshot: CampanhaProSnapshot) -> dict | None:
    """Coleta dados do dossiê próprio para alimentar digital_sentiment e
    media_coverage no mapper. Retorna None quando não há dossiê 'own' pronto."""
    project = (
        db.query(PoliticalProject)
        .filter(
            PoliticalProject.organization_id == snapshot.organization_id,
            PoliticalProject.campaign_id == snapshot.campaign_id,
        )
        .order_by(PoliticalProject.created_at.asc())
        .first()
    )
    if project is None:
        return None
    dossier = (
        db.query(CandidateDossier)
        .filter(
            CandidateDossier.political_project_id == project.id,
            CandidateDossier.candidate_type == "own",
            CandidateDossier.status == "ready",
        )
        .order_by(CandidateDossier.last_refreshed_at.desc().nullslast())
        .first()
    )
    if dossier is None:
        return None
    snaps = (
        db.query(DossierSocialSnapshot)
        .filter(DossierSocialSnapshot.dossier_id == dossier.id)
        .all()
    )
    return {
        "social_snapshots": [
            {
                "platform": s.platform,
                "sentiment_distribution": s.sentiment_distribution or {},
            }
            for s in snaps
        ],
        "recent_news": dossier.recent_news or [],
    }


def _process(db: Session, snapshot_id: str) -> str:
    snapshot = (
        db.query(CampanhaProSnapshot)
        .filter(CampanhaProSnapshot.id == snapshot_id)
        .first()
    )
    if snapshot is None:
        logger.warning("snapshot_not_found", extra={"snapshot_id": snapshot_id})
        return "snapshot_not_found"

    if snapshot.schema_version != "campanhapro.snapshot.v1" or not snapshot.campaign_id:
        logger.info(
            "snapshot_not_v1_skipped",
            extra={
                "snapshot_id": snapshot_id,
                "schema_version": snapshot.schema_version,
            },
        )
        return "skipped_legacy"

    repo = CampanhaProFactorCacheRepository(db)
    if repo.get_by_snapshot(snapshot.id) is not None:
        logger.info("factor_cache_already_present", extra={"snapshot_id": snapshot.id})
        return "already_cached"

    own_dossier_context = _own_dossier_context(db, snapshot)
    result = map_snapshot_to_factors(snapshot.payload or {}, own_dossier=own_dossier_context)

    # Encontra o projeto associado a essa campanha para popular FK opcional.
    project = (
        db.query(PoliticalProject)
        .filter(
            PoliticalProject.organization_id == snapshot.organization_id,
            PoliticalProject.campaign_id == snapshot.campaign_id,
        )
        .order_by(PoliticalProject.created_at.asc())
        .first()
    )

    cache = CampanhaProFactorCache(
        id=str(uuid4()),
        organization_id=snapshot.organization_id,
        campaign_id=snapshot.campaign_id,
        political_project_id=project.id if project else None,
        snapshot_id=snapshot.id,
        reference_date=snapshot.reference_date or datetime.utcnow(),
        factors=result["factors"],
        coverage_percent=result["coverage_percent"],
        sources_used=result["sources_used"],
        warnings=result["warnings"],
    )
    repo.add(cache)

    # Branding: popula colunas no projeto a partir do snapshot quando vazias.
    # Os campos físicos só serão criados pela migration da Fase 5; aqui
    # fazemos getattr com setattr defensivo para não acoplar Fase 2 a
    # tabelas futuras. Quando a Fase 5 adicionar as colunas, esta lógica
    # já funcionará sem mudança.
    if project is not None:
        details = ((snapshot.payload or {}).get("campaign") or {}).get("details") or {}
        for col_name, payload_key in (
            ("candidate_photo_url", "candidatePhotoUrl"),
            ("header_logo_url", "headerLogo"),
            ("footer_logo_url", "footerLogo"),
        ):
            if hasattr(project, col_name):
                if not getattr(project, col_name) and details.get(payload_key):
                    setattr(project, col_name, details[payload_key])
        db.commit()

    _audit(
        db,
        organization_id=snapshot.organization_id,
        project_id=project.id if project else None,
        action="factors.cached",
        payload={
            "snapshot_id": snapshot.id,
            "campaign_id": snapshot.campaign_id,
            "coverage_percent": result["coverage_percent"],
            "factors_present": list(result["factors"].keys()),
            "warnings_count": len(result["warnings"]),
        },
    )

    logger.info(
        "factors_cached",
        extra={
            "snapshot_id": snapshot.id,
            "campaign_id": snapshot.campaign_id,
            "coverage": result["coverage_percent"],
        },
    )
    return "cached"


@celery_app.task(
    name="app.workers.snapshot_tasks.process_snapshot_factors",
    bind=True,
    max_retries=3,
)
def process_snapshot_factors(self, snapshot_id: str) -> str:  # noqa: ANN001
    """Lê snapshot, aplica mapper, grava cache + audit log.

    Em testes (eager mode) usa a sessão do TestClient via override.
    Em produção abre uma sessão própria (worker não vive dentro do request).
    """
    try:
        with SessionLocal() as db:
            return _process(db, snapshot_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("process_snapshot_factors_failed", extra={"snapshot_id": snapshot_id})
        raise self.retry(exc=exc, countdown=10)
