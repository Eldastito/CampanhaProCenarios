"""Celery task que executa o pipeline do Dossiê (Fase 3b PRD v2).

Despachada pelos endpoints ``POST /dossiers`` e
``POST /dossiers/{id}/refresh``. Em testes roda eager.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.dossier import CandidateDossier
from app.models.political import PoliticalAuditLog
from app.services.dossier.dossier_orchestrator import run_pipeline
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _audit(db, *, organization_id, project_id, action, payload):
    db.add(
        PoliticalAuditLog(
            id=str(uuid4()),
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=None,
            action=action,
            target_type="candidate_dossier",
            target_id=payload.get("dossier_id"),
            payload=payload,
        )
    )
    db.commit()


@celery_app.task(
    name="app.workers.dossier_tasks.generate_dossier_task",
    bind=True,
    max_retries=2,
)
def generate_dossier_task(self, dossier_id: str) -> str:  # noqa: ANN001
    """Executa o pipeline e registra audit log final."""
    try:
        with SessionLocal() as db:
            dossier = (
                db.query(CandidateDossier)
                .filter(CandidateDossier.id == dossier_id)
                .first()
            )
            if dossier is None:
                logger.warning("dossier_not_found", extra={"dossier_id": dossier_id})
                return "dossier_not_found"

            run_pipeline(db, dossier)

            _audit(
                db,
                organization_id=dossier.organization_id,
                project_id=dossier.political_project_id,
                action=(
                    "dossier.generated" if dossier.status == "ready" else "dossier.failed"
                ),
                payload={
                    "dossier_id": dossier.id,
                    "candidate_name": dossier.candidate_name,
                    "candidate_type": dossier.candidate_type,
                    "status": dossier.status,
                    "confidence_level": dossier.confidence_level,
                    "sources_count": len(dossier.sources),
                },
            )
            return dossier.status
    except Exception as exc:  # noqa: BLE001
        logger.exception("generate_dossier_task_failed", extra={"dossier_id": dossier_id})
        raise self.retry(exc=exc, countdown=15)
