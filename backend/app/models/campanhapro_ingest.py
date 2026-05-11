from datetime import datetime

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class CampanhaProEvent(Base):
    """Persisted CampanhaPro event received via /campanhapro/ingest/events."""

    __tablename__ = "campanhapro_events"

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


class CampanhaProSnapshot(Base):
    """Persisted CampanhaPro snapshot received via /campanhapro/ingest/snapshots."""

    __tablename__ = "campanhapro_snapshots"

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

    # PRD v2 / Fase 1 — contrato `campanhapro.snapshot.v1`.
    # Ambos nullable para preservar registros legados (v0 sem schemaVersion).
    # A Fase 2 só processa snapshots com campaign_id presente.
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
