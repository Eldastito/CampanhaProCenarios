"""Registro de chamadas do orquestrador Claude Managed (Fase 6 PRD v2)."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class ScenarioOrchestratorCall(Base):
    """Uma execução do endpoint /scenarios/generate.

    Guarda prompt original, lista de agentes consultados, cenário gerado
    (FK opcional — pode ser None se a geração falhou antes da criação),
    payload retornado pelo Claude, análises por agente e modelo LLM
    usado. Auditoria + base do rate limit.
    """

    __tablename__ = "scenario_orchestrator_calls"

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

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    agents_consulted: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    scenario_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )
    scenario_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    agents_analyses: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="completed"
    )  # completed | failed | rate_limited
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
