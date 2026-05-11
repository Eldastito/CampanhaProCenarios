"""Worker do Monte Carlo de probabilidade de eleição (Fase 4 PRD v2)."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.election_probability import ElectionProbabilityResult
from app.models.political import PoliticalAuditLog
from app.services.election_probability_service import simulate_election
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
            target_type="election_probability_result",
            target_id=payload.get("result_id"),
            payload=payload,
        )
    )
    db.commit()


@celery_app.task(
    name="app.workers.election_tasks.run_election_probability",
    bind=True,
    max_retries=2,
)
def run_election_probability(self, result_id: str) -> str:  # noqa: ANN001
    """Executa o Monte Carlo gravando o resultado na linha já criada
    com status='queued'."""
    try:
        with SessionLocal() as db:
            row = (
                db.query(ElectionProbabilityResult)
                .filter(ElectionProbabilityResult.id == result_id)
                .first()
            )
            if row is None:
                logger.warning("election_result_not_found", extra={"id": result_id})
                return "not_found"

            row.status = "running"
            db.commit()

            try:
                payload = simulate_election(
                    row.input_candidates,
                    office=row.office,
                    iterations=row.iterations,
                    seed=row.seed,
                )
            except ValueError as exc:
                row.status = "failed"
                row.error_message = str(exc)
                row.completed_at = datetime.utcnow()
                db.commit()
                _audit(
                    db,
                    organization_id=row.organization_id,
                    project_id=row.political_project_id,
                    action="election_probability.failed",
                    payload={"result_id": row.id, "error": str(exc)},
                )
                return "failed"

            row.output_results = payload["results"]
            row.confidence_level = payload["confidence_level"]
            row.status = "completed"
            row.error_message = None
            row.completed_at = datetime.utcnow()
            db.commit()
            _audit(
                db,
                organization_id=row.organization_id,
                project_id=row.political_project_id,
                action="election_probability.completed",
                payload={
                    "result_id": row.id,
                    "office": row.office,
                    "iterations": row.iterations,
                    "candidates": [c.get("name") for c in row.input_candidates],
                    "winners_top": sorted(
                        payload["results"],
                        key=lambda r: r["win_probability"],
                        reverse=True,
                    )[:3],
                },
            )
            return "completed"
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_election_probability_failed", extra={"id": result_id})
        raise self.retry(exc=exc, countdown=10)
