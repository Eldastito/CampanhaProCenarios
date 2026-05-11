"""campanhapro_factor_cache

Revision ID: 20260510_0012
Revises: 20260510_0011
Create Date: 2026-05-10 16:00:00

Fase 2 do PRD v2: cache de fatores derivado do snapshot v1.

Cada snapshot processado produz uma linha aqui com:
- factors: dict {key: 0..100} apenas para fatores que tiveram dado real
  (fatores ausentes ficam fora — não preencher com 0).
- coverage_percent: % dos 12 fatores eleitorais que foram preenchidos.
- sources_used: dict {factor_key: ["pesquisa", "visits", ...]} — rastreabilidade.
- warnings: lista de strings com observações (amostra pequena, dado parcial, etc).

A query mais comum é "último cache para campanha X / projeto Y" — daí o
índice composto (organization_id, campaign_id, reference_date desc).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0012"
down_revision: Union[str, None] = "20260510_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campanhapro_factor_cache",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("campaign_id", sa.String(length=64), nullable=False),
        sa.Column("political_project_id", sa.String(length=64), nullable=True),
        sa.Column("snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("reference_date", sa.DateTime(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=False),
        sa.Column("coverage_percent", sa.Float(), nullable=False),
        sa.Column("sources_used", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["political_project_id"], ["political_projects.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["campanhapro_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_campanhapro_factor_cache_organization_id",
        "campanhapro_factor_cache",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_campanhapro_factor_cache_campaign_id",
        "campanhapro_factor_cache",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_campanhapro_factor_cache_political_project_id",
        "campanhapro_factor_cache",
        ["political_project_id"],
        unique=False,
    )
    op.create_index(
        "ix_campanhapro_factor_cache_snapshot_id",
        "campanhapro_factor_cache",
        ["snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_campanhapro_factor_cache_org_campaign_ref",
        "campanhapro_factor_cache",
        ["organization_id", "campaign_id", "reference_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campanhapro_factor_cache_org_campaign_ref",
        table_name="campanhapro_factor_cache",
    )
    op.drop_index(
        "ix_campanhapro_factor_cache_snapshot_id",
        table_name="campanhapro_factor_cache",
    )
    op.drop_index(
        "ix_campanhapro_factor_cache_political_project_id",
        table_name="campanhapro_factor_cache",
    )
    op.drop_index(
        "ix_campanhapro_factor_cache_campaign_id",
        table_name="campanhapro_factor_cache",
    )
    op.drop_index(
        "ix_campanhapro_factor_cache_organization_id",
        table_name="campanhapro_factor_cache",
    )
    op.drop_table("campanhapro_factor_cache")
