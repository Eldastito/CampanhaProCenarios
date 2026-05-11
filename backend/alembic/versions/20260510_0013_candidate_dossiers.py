"""candidate_dossiers + dossier_social_snapshots

Revision ID: 20260510_0013
Revises: 20260510_0012
Create Date: 2026-05-10 20:00:00

Fase 3a do PRD v2 — modelos do Dossiê de Candidato.

- ``candidate_dossiers``: 1 linha por candidato (próprio ou adversário)
  vinculado a um political_project. Status (``queued|running|ready|failed``)
  permite ao front saber se o orquestrador da Fase 3b já terminou.
- ``dossier_social_snapshots``: histórico de métricas sociais por
  plataforma. ``source`` indica a origem (api Meta Graph, manual ou
  llm_estimate via web search). Sem chaves pagas no MVP.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0013"
down_revision: Union[str, None] = "20260510_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "candidate_dossiers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("political_project_id", sa.String(length=64), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=False),
        sa.Column("candidate_type", sa.String(length=32), nullable=False),
        sa.Column("party", sa.String(length=100), nullable=True),
        sa.Column("office", sa.String(length=100), nullable=False),
        sa.Column("tse_candidate_id", sa.String(length=64), nullable=True),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("political_history", sa.JSON(), nullable=False),
        sa.Column("current_mandates", sa.JSON(), nullable=False),
        sa.Column("platform_and_proposals", sa.JSON(), nullable=False),
        sa.Column("legal_issues", sa.JSON(), nullable=False),
        sa.Column("ficha_limpa_status", sa.String(length=50), nullable=True),
        sa.Column("recent_news", sa.JSON(), nullable=False),
        sa.Column("media_presence", sa.JSON(), nullable=False),
        sa.Column("social_metrics", sa.JSON(), nullable=False),
        sa.Column("rejection_drivers", sa.JSON(), nullable=False),
        sa.Column("strength_drivers", sa.JSON(), nullable=False),
        sa.Column("swot", sa.JSON(), nullable=False),
        sa.Column("confidence_level", sa.String(length=20), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("generated_by_ai", sa.Boolean(), nullable=False),
        sa.Column("llm_models_used", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["political_project_id"],
            ["political_projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_candidate_dossiers_organization_id",
        "candidate_dossiers",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_dossiers_political_project_id",
        "candidate_dossiers",
        ["political_project_id"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_dossiers_tse_candidate_id",
        "candidate_dossiers",
        ["tse_candidate_id"],
        unique=False,
    )

    op.create_table(
        "dossier_social_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("dossier_id", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("handle", sa.String(length=255), nullable=False),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("posts_last_30d", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("avg_likes", sa.Float(), nullable=True),
        sa.Column("avg_comments", sa.Float(), nullable=True),
        sa.Column("top_posts", sa.JSON(), nullable=False),
        sa.Column("sentiment_distribution", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dossier_id"],
            ["candidate_dossiers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dossier_social_snapshots_dossier_id",
        "dossier_social_snapshots",
        ["dossier_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dossier_social_snapshots_dossier_id",
        table_name="dossier_social_snapshots",
    )
    op.drop_table("dossier_social_snapshots")
    op.drop_index(
        "ix_candidate_dossiers_tse_candidate_id",
        table_name="candidate_dossiers",
    )
    op.drop_index(
        "ix_candidate_dossiers_political_project_id",
        table_name="candidate_dossiers",
    )
    op.drop_index(
        "ix_candidate_dossiers_organization_id",
        table_name="candidate_dossiers",
    )
    op.drop_table("candidate_dossiers")
