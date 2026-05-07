from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.campanhapro_ingest import CampanhaProEvent, CampanhaProSnapshot


class CampanhaProIngestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def event_request_id_exists(self, request_id: str) -> bool:
        return (
            self.db.query(CampanhaProEvent.id)
            .filter(CampanhaProEvent.request_id == request_id)
            .first()
            is not None
        )

    def add_event(self, event: CampanhaProEvent) -> CampanhaProEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def try_add_event(self, event: CampanhaProEvent) -> tuple[CampanhaProEvent, bool]:
        """Add event; return (event, created). created=False means duplicate."""
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event, True
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(CampanhaProEvent)
                .filter(CampanhaProEvent.request_id == event.request_id)
                .first()
            )
            return existing, False  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot_request_id_exists(self, request_id: str) -> bool:
        return (
            self.db.query(CampanhaProSnapshot.id)
            .filter(CampanhaProSnapshot.request_id == request_id)
            .first()
            is not None
        )

    def add_snapshot(self, snapshot: CampanhaProSnapshot) -> CampanhaProSnapshot:
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def try_add_snapshot(self, snapshot: CampanhaProSnapshot) -> tuple[CampanhaProSnapshot, bool]:
        """Add snapshot; return (snapshot, created). created=False means duplicate."""
        try:
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot, True
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(CampanhaProSnapshot)
                .filter(CampanhaProSnapshot.request_id == snapshot.request_id)
                .first()
            )
            return existing, False  # type: ignore[return-value]

    def get_latest_snapshot_for_org(
        self, organization_id: str, snapshot_type: str | None = None
    ) -> CampanhaProSnapshot | None:
        """Return the most recent snapshot for *organization_id*, optionally filtered by type."""
        q = self.db.query(CampanhaProSnapshot).filter(
            CampanhaProSnapshot.organization_id == organization_id
        )
        if snapshot_type:
            q = q.filter(CampanhaProSnapshot.snapshot_type == snapshot_type)
        return q.order_by(CampanhaProSnapshot.reference_date.desc()).first()
