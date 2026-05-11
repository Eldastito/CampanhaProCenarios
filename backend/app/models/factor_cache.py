"""Cache de fatores eleitorais derivados de snapshots CampanhaPro (Fase 2 PRD v2)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class CampanhaProFactorCache(Base):
    """Cache do mapeamento snapshot → 12 fatores eleitorais.

    Cada snapshot v1 processado pelo worker gera uma linha aqui. A query
    canônica é "último cache para campanha X / projeto Y" — usar o índice
    composto ``ix_campanhapro_factor_cache_org_campaign_ref``.
    """

    __tablename__ = "campanhapro_factor_cache"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    political_project_id: Mapped[str | None] = mapped_column(
        ForeignKey("political_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("campanhapro_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reference_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    factors: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    coverage_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sources_used: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
