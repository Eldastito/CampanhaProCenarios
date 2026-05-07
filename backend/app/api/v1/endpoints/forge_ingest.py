"""FORGE platform ingest endpoints.

Events and snapshots sent by the FORGE platform are persisted for use in
prediction scoring and future feature engineering.  Duplicate submissions
(same request_id) are accepted idempotently.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.internal import require_internal_ingest_secret
from app.db.session import get_db
from app.models.forge_ingest import ForgeEvent, ForgeSnapshot
from app.repositories.forge_ingest_repository import ForgeIngestRepository
from app.schemas.ingest import (
    ForgeEventIngestPayload,
    ForgeSnapshotIngestPayload,
    IngestAcceptedResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/ingest/events",
    response_model=IngestAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest FORGE events",
)
def ingest_events(
    body: ForgeEventIngestPayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_ingest_secret),
) -> IngestAcceptedResponse:
    repo = ForgeIngestRepository(db)
    request_id_str = str(body.request_id)

    event = ForgeEvent(
        id=str(uuid4()),
        request_id=request_id_str,
        source_system=body.source_system,
        organization_id=body.organization_id,
        event_type=body.event_type,
        occurred_at=body.occurred_at,
        payload_version=body.payload_version,
        payload=body.payload,
    )
    _, created = repo.try_add_event(event)

    if created:
        logger.info(
            "forge_event_persisted",
            extra={
                "request_id": request_id_str,
                "org": body.organization_id,
                "event_type": body.event_type,
            },
        )
    else:
        logger.info(
            "forge_event_duplicate_ignored",
            extra={"request_id": request_id_str},
        )

    return IngestAcceptedResponse(
        request_id=body.request_id,
        detail="Event persisted successfully." if created else "Duplicate request_id — event already recorded.",
    )


@router.post(
    "/ingest/snapshots",
    response_model=IngestAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest FORGE snapshots",
)
def ingest_snapshots(
    body: ForgeSnapshotIngestPayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_internal_ingest_secret),
) -> IngestAcceptedResponse:
    repo = ForgeIngestRepository(db)
    request_id_str = str(body.request_id)

    snapshot = ForgeSnapshot(
        id=str(uuid4()),
        request_id=request_id_str,
        source_system=body.source_system,
        organization_id=body.organization_id,
        snapshot_type=body.snapshot_type,
        reference_date=body.reference_date,
        payload_version=body.payload_version,
        payload=body.payload,
    )
    _, created = repo.try_add_snapshot(snapshot)

    if created:
        logger.info(
            "forge_snapshot_persisted",
            extra={
                "request_id": request_id_str,
                "org": body.organization_id,
                "snapshot_type": body.snapshot_type,
            },
        )
    else:
        logger.info(
            "forge_snapshot_duplicate_ignored",
            extra={"request_id": request_id_str},
        )

    return IngestAcceptedResponse(
        request_id=body.request_id,
        detail="Snapshot persisted successfully." if created else "Duplicate request_id — snapshot already recorded.",
    )
