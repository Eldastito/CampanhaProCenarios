"""Modelos de dossiê de candidato (Fase 3 PRD v2).

Dois modelos:
- ``CandidateDossier``: registro estruturado do candidato (próprio ou
  adversário) consolidado por LLM a partir de fontes públicas gratuitas
  (web search via LLM, RSS, TSE Open Data, Meta Graph API para próprio).
- ``DossierSocialSnapshot``: snapshots de métricas de redes sociais
  associados a um dossiê. Para adversários a coleta vem por entrada
  manual + extração por LLM via URLs públicas (sem APIs pagas).

PRD §3.1: campos estruturados rastreáveis. ``sources`` preserva URLs
para que cada afirmação possa ser auditada (FATO vs INFERÊNCIA vs
HIPÓTESE). ``generated_by_ai=True`` por default — o front exibe esse
sinal sem ambiguidade.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class CandidateDossier(Base):
    """Dossiê estruturado de um candidato (próprio ou adversário)."""

    __tablename__ = "candidate_dossiers"

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

    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "own" | "opponent"
    party: Mapped[str | None] = mapped_column(String(100), nullable=True)
    office: Mapped[str] = mapped_column(String(100), nullable=False)
    tse_candidate_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Campos estruturados do dossiê. JSON aceita ausência (None) quando
    # o pipeline ainda não preencheu — o front renderiza skeleton.
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    political_history: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_mandates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    platform_and_proposals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    legal_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ficha_limpa_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recent_news: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    media_presence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    social_metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rejection_drivers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    strength_drivers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    swot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    confidence_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    llm_models_used: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
    )  # queued | running | ready | failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class DossierSocialSnapshot(Base):
    """Métricas de redes sociais coletadas em um momento específico."""

    __tablename__ = "dossier_social_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dossier_id: Mapped[str] = mapped_column(
        ForeignKey("candidate_dossiers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)  # instagram | tiktok | twitter | facebook
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posts_last_30d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_likes: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_comments: Mapped[float | None] = mapped_column(Float, nullable=True)
    top_posts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sentiment_distribution: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Origem do dado: ``api`` (Meta Graph para candidato próprio),
    # ``manual`` (operador colou no dossiê de adversário) ou
    # ``llm_estimate`` (LLM extraiu de URL pública).
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, nullable=False
    )
