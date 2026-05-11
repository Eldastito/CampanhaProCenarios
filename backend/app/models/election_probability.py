"""Resultado do Monte Carlo de probabilidade de eleição (Fase 4 PRD v2)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class ElectionProbabilityResult(Base):
    """Uma execução do Monte Carlo para uma disputa de N candidatos.

    ``input_candidates`` preserva exatamente o que foi enviado (nome,
    fatores 0-100, confidence). ``output_results`` traz por candidato:
    win_probability, mean_share, share_ci_95, second_round_*. ``seed``
    + ``input_candidates`` permitem reproduzir o resultado.
    """

    __tablename__ = "election_probability_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    political_project_id: Mapped[str] = mapped_column(
        ForeignKey("political_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    office: Mapped[str] = mapped_column(String(100), nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued"
    )  # queued | running | completed | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_candidates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    output_results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
