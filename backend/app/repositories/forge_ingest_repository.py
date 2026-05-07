from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.forge_ingest import ForgeEvent, ForgeSnapshot


class ForgeIngestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def event_request_id_exists(self, request_id: str) -> bool:
        return (
            self.db.query(ForgeEvent.id)
            .filter(ForgeEvent.request_id == request_id)
            .first()
            is not None
        )

    def add_event(self, event: ForgeEvent) -> ForgeEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def try_add_event(self, event: ForgeEvent) -> tuple[ForgeEvent, bool]:
        """Add event; return (event, created). created=False means duplicate."""
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event, True
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(ForgeEvent)
                .filter(ForgeEvent.request_id == event.request_id)
                .first()
            )
            return existing, False  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def snapshot_request_id_exists(self, request_id: str) -> bool:
        return (
            self.db.query(ForgeSnapshot.id)
            .filter(ForgeSnapshot.request_id == request_id)
            .first()
            is not None
        )

    def add_snapshot(self, snapshot: ForgeSnapshot) -> ForgeSnapshot:
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def try_add_snapshot(self, snapshot: ForgeSnapshot) -> tuple[ForgeSnapshot, bool]:
        """Add snapshot; return (snapshot, created). created=False means duplicate."""
        try:
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot, True
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(ForgeSnapshot)
                .filter(ForgeSnapshot.request_id == snapshot.request_id)
                .first()
            )
            return existing, False  # type: ignore[return-value]

    def get_latest_snapshot_for_org(
        self, organization_id: str, snapshot_type: str | None = None
    ) -> ForgeSnapshot | None:
        """Return the most recent snapshot for *organization_id*, optionally filtered by type."""
        q = self.db.query(ForgeSnapshot).filter(
            ForgeSnapshot.organization_id == organization_id
        )
        if snapshot_type:
            q = q.filter(ForgeSnapshot.snapshot_type == snapshot_type)
        return q.order_by(ForgeSnapshot.reference_date.desc()).first()
