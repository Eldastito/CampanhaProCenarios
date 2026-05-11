"""political_projects.campaign_id

Revision ID: 20260510_0010
Revises: 20260509_0009
Create Date: 2026-05-10 00:00:00

Fase 0 do PRD v2: introduz ``campaign_id`` em ``political_projects``.

Estratégia para tornar a coluna NOT NULL sem quebrar dados existentes:
1. Adiciona a coluna como nullable.
2. Backfill ``campaign_id = id`` (1 projeto = 1 campanha histórica) — isto preserva
   os projetos pré-v2, que viviam sem o conceito de campanha.
3. Aplica NOT NULL.
4. Cria índice composto ``(organization_id, campaign_id)`` para suportar a
   quota MVP (10 campanhas por organização) e o isolamento exigido pelo PRD.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0010"
down_revision: Union[str, None] = "20260509_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "political_projects",
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE political_projects SET campaign_id = id WHERE campaign_id IS NULL"
    )
    op.alter_column(
        "political_projects",
        "campaign_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_index(
        "ix_political_projects_campaign_id",
        "political_projects",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_projects_org_campaign",
        "political_projects",
        ["organization_id", "campaign_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_political_projects_org_campaign", table_name="political_projects")
    op.drop_index("ix_political_projects_campaign_id", table_name="political_projects")
    op.drop_column("political_projects", "campaign_id")
