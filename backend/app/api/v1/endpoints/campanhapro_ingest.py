"""CampanhaPro platform ingest endpoints.

Snapshots sent by the CampanhaPro platform are persisted for use in
political scenario scoring. Duplicate submissions (same request_id) are
accepted idempotently.

PRD v2 / Fase 1: o endpoint discrimina pelo campo ``schemaVersion``:
- ``"campanhapro.snapshot.v1"`` → parseia como ``SnapshotV1Payload``,
  exige ``snapshotId``, ``campaignId``, ``organizationId``, ``generatedAt``.
- ausente → mantém formato legado (``snapshot_type``, ``reference_date``).

A Fase 2 (mapper) só processa snapshots que tenham ``campaign_id`` populado
— ou seja, snapshots v1.
"""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth.internal import require_campanhapro_ingest_secret
from app.db.session import get_db
from app.models.campanhapro_ingest import CampanhaProSnapshot
from app.repositories.campanhapro_ingest_repository import CampanhaProIngestRepository
from app.schemas.ingest import (
    SNAPSHOT_V1_SCHEMA_VERSION,
    CampanhaProSnapshotIngestPayload,
    IngestAcceptedResponse,
    SnapshotV1Payload,
)
from app.workers.snapshot_tasks import process_snapshot_factors

logger = logging.getLogger(__name__)
router = APIRouter()


def _build_v1_snapshot(parsed: SnapshotV1Payload, raw_body: dict[str, Any]) -> CampanhaProSnapshot:
    return CampanhaProSnapshot(
        id=str(uuid4()),
        request_id=str(parsed.snapshot_id),
        source_system="CAMPANHAPRO",
        organization_id=parsed.organization_id,
        snapshot_type="snapshot_v1",
        reference_date=parsed.generated_at.replace(tzinfo=None)
        if parsed.generated_at.tzinfo is not None
        else parsed.generated_at,
        payload_version="v1",
        payload=raw_body,
        campaign_id=parsed.campaign_id,
        schema_version=parsed.schema_version,
    )


def _build_legacy_snapshot(parsed: CampanhaProSnapshotIngestPayload) -> CampanhaProSnapshot:
    return CampanhaProSnapshot(
        id=str(uuid4()),
        request_id=str(parsed.request_id),
        source_system="CAMPANHAPRO",
        organization_id=parsed.organization_id,
        snapshot_type=parsed.snapshot_type,
        reference_date=parsed.reference_date,
        payload_version=parsed.payload_version,
        payload=parsed.payload,
        # Legados não tem campaign_id; ficam fora do mapper da Fase 2.
        campaign_id=None,
        schema_version=None,
    )


@router.post(
    "/ingest/snapshots",
    response_model=IngestAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest CampanhaPro snapshots (v1 ou legado)",
)
def ingest_campanhapro_snapshots(
    body: dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_campanhapro_ingest_secret),
) -> IngestAcceptedResponse:
    is_v1 = body.get("schemaVersion") == SNAPSHOT_V1_SCHEMA_VERSION

    try:
        if is_v1:
            parsed_v1 = SnapshotV1Payload.model_validate(body)
            snapshot = _build_v1_snapshot(parsed_v1, body)
            request_uuid = parsed_v1.snapshot_id
            log_extra = {
                "schema_version": parsed_v1.schema_version,
                "campaign_id": parsed_v1.campaign_id,
                "org": parsed_v1.organization_id,
            }
        else:
            parsed_legacy = CampanhaProSnapshotIngestPayload.model_validate(body)
            snapshot = _build_legacy_snapshot(parsed_legacy)
            request_uuid = parsed_legacy.request_id
            log_extra = {
                "schema_version": "legacy",
                "snapshot_type": parsed_legacy.snapshot_type,
                "org": parsed_legacy.organization_id,
            }
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    repo = CampanhaProIngestRepository(db)
    _, created = repo.try_add_snapshot(snapshot)

    if created:
        logger.info("campanhapro_snapshot_persisted", extra={**log_extra, "request_id": str(request_uuid)})
        # Despacha mapper para Celery (Fase 2). Em testes roda síncrono
        # via task_always_eager. Só faz sentido para v1 — o worker
        # ignora snapshots legados sem campaign_id.
        if is_v1:
            try:
                process_snapshot_factors.delay(snapshot.id)
            except Exception:  # noqa: BLE001
                # Não falhar o request se o broker estiver indisponível;
                # o snapshot já está persistido e pode ser reprocessado.
                logger.exception("celery_dispatch_failed", extra={"snapshot_id": snapshot.id})
    else:
        logger.info("campanhapro_snapshot_duplicate_ignored", extra={**log_extra, "request_id": str(request_uuid)})

    detail = (
        "Snapshot persisted successfully."
        if created
        else "Duplicate request_id — snapshot already recorded."
    )
    return IngestAcceptedResponse(request_id=request_uuid, detail=detail)
