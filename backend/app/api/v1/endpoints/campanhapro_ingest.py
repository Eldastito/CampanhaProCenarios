"""CampanhaPro platform ingest endpoints.

Snapshots sent by the CampanhaPro platform are persisted for use in
political scenario scoring. Duplicate submissions (same request_id)
are accepted idempotently.
"""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.internal import require_campanhapro_ingest_secret
from app.db.session import get_db
from app.models.campanhapro_ingest import CampanhaProSnapshot
from app.repositories.campanhapro_ingest_repository import CampanhaProIngestRepository
from app.schemas.ingest import CampanhaProSnapshotIngestPayload, IngestAcceptedResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/ingest/snapshots",
    response_model=IngestAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest CampanhaPro snapshots",
)
def ingest_campanhapro_snapshots(
    body: CampanhaProSnapshotIngestPayload,
    db: Session = Depends(get_db),
    _: str = Depends(require_campanhapro_ingest_secret),
) -> IngestAcceptedResponse:
    repo = CampanhaProIngestRepository(db)
    request_id_str = str(body.request_id)

    snapshot = CampanhaProSnapshot(
        id=str(uuid4()),
        request_id=request_id_str,
        source_system="CAMPANHAPRO",
        organization_id=body.organization_id,
        snapshot_type=body.snapshot_type,
        reference_date=body.reference_date,
        payload_version=body.payload_version,
        payload=body.payload,
    )
    _, created = repo.try_add_snapshot(snapshot)

    if created:
        logger.info(
            "campanhapro_snapshot_persisted",
            extra={
                "request_id": request_id_str,
                "org": body.organization_id,
                "snapshot_type": body.snapshot_type,
            },
        )
    else:
        logger.info(
            "campanhapro_snapshot_duplicate_ignored",
            extra={"request_id": request_id_str},
        )

    return IngestAcceptedResponse(
        request_id=body.request_id,
        detail="Snapshot persisted successfully." if created else "Duplicate request_id — snapshot already recorded.",
    )
