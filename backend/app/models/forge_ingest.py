from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class ForgeEvent(Base):
    """Persisted FORGE event received via /forge/ingest/events."""

    __tablename__ = "forge_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Idempotency key — duplicate request_ids are rejected
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payload_version: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)


class ForgeSnapshot(Base):
    """Persisted FORGE snapshot received via /forge/ingest/snapshots."""

    __tablename__ = "forge_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Idempotency key — duplicate request_ids are rejected
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    source_system: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reference_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    payload_version: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now_naive)
