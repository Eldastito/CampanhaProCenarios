"""Modelos do domínio político-eleitoral.

Tabelas centrais para o produto CampanhaPro Cenários.  Cada projeto eleitoral
agrupa evidências, agentes, simulações e relatórios.  As tabelas auxiliares
de auditoria/compliance suportam os guardrails exigidos pelo TSE/LGPD.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now_naive
from app.db.base import Base


class PoliticalProject(Base):
    """Projeto eleitoral — agrupa cenários, evidências e simulações de uma campanha."""

    __tablename__ = "political_projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    # Identificador externo da campanha no CampanhaPro. É a chave de
    # isolamento exigida pelo PRD v2: snapshots, dossiês, cache de fatores
    # e relatórios são todos escopados por (organization_id, campaign_id).
    # Para projetos criados antes do v2 o backfill da migration 0010
    # define campaign_id = id (1 projeto = 1 campanha histórica).
    campaign_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Identidade da disputa
    election_year: Mapped[int] = mapped_column(Integer, nullable=False)
    office: Mapped[str] = mapped_column(String(100), nullable=False)  # ex: "Prefeito", "Vereador"
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(255), nullable=True)

    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    parties: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    known_opponents: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    horizon_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    # Fase 5 PRD v2 — branding usado em relatórios PDF/DOCX. Populado
    # automaticamente pelo mapper da Fase 2 a partir de campaign.details
    # do snapshot v1; pode ser sobrescrito manualmente via PATCH do projeto.
    header_logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    footer_logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    candidate_photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )


class PoliticalEvidenceSource(Base):
    """Evidência (documento, link, pesquisa) anexada a um projeto eleitoral.

    O conteúdo extraído fica em ``raw_text``; o arquivo bruto é referenciado por
    ``storage_uri``.  ``reliability_level`` segue a classificação do PRD
    (oficial, imprensa, pesquisa registrada, base pública, interno, social, não verificada).
    """

    __tablename__ = "political_evidence_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("political_projects.id"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf|txt|md|csv|link|manual
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    reliability_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unverified",
    )  # official|press|registered_poll|public_base|internal|social|unverified

    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    storage_uri: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
    )  # pending|processing|ready|failed
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class PoliticalComplianceAlert(Base):
    """Alerta de compliance gerado por guardrails (TSE, LGPD, fonte fraca, etc.)."""

    __tablename__ = "political_compliance_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("political_projects.id"),
        nullable=True,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # ex: claim_without_source, deepfake_risk, sensitive_personal_data,
    #     poll_missing_metadata, certainty_language, weak_source

    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")  # low|medium|high|critical
    message: Mapped[str] = mapped_column(Text, nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")  # open|acknowledged|resolved|dismissed
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class PoliticalAuditLog(Base):
    """Trilha de auditoria do domínio político: quem fez o quê, quando e em qual contexto."""

    __tablename__ = "political_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("political_projects.id"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # ex: project.created, evidence.uploaded, simulation.started, report.exported

    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)


class PoliticalAgentProfile(Base):
    """Perfil de agente político (Fase 4).

    Dois sabores via ``agent_type``:
    - ``fixed_specialist``: bancada estável de especialistas (jurídico,
      fact-checking, mídia, território, etc.). Catálogo estático em
      ``app.services.political_agents_catalog``.
    - ``generated``: persona derivada de entidades do grafo
      (eleitor, liderança, influenciador) — atrelada a source_node_ids
      e source_evidence_ids para rastreabilidade.

    O ``persona_prompt`` é o texto-base usado quando a UI conversar com
    o agente (Fase 4 cont. / Fase 5). Vieses e limitações declarados
    aparecem na UI antes de qualquer interação (PRD §RF-07 e §7).
    """

    __tablename__ = "political_agent_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("political_projects.id"),
        nullable=False,
        index=True,
    )

    agent_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        default="fixed_specialist",
    )
    role: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    synthetic_name: Mapped[str] = mapped_column(String(150), nullable=False)
    biography: Mapped[str] = mapped_column(Text, nullable=False)
    persona_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    biases_declared: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    limitations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")

    source_node_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
