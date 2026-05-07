"""political_agent_profiles

Revision ID: 20260509_0009
Revises: 20260508_0008
Create Date: 2026-05-09 00:00:00

Cria a tabela de bancada de agentes políticos (Fase 4):
fixed specialists + agentes derivados do grafo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0009"
down_revision: Union[str, None] = "20260508_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "political_agent_profiles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("agent_type", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("synthetic_name", sa.String(length=150), nullable=False),
        sa.Column("biography", sa.Text(), nullable=False),
        sa.Column("persona_prompt", sa.Text(), nullable=False),
        sa.Column("biases_declared", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("confidence_level", sa.String(length=20), nullable=False),
        sa.Column("source_node_ids", sa.JSON(), nullable=False),
        sa.Column("source_evidence_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["political_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_political_agent_profiles_organization_id",
        "political_agent_profiles",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_agent_profiles_project_id",
        "political_agent_profiles",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_agent_profiles_agent_type",
        "political_agent_profiles",
        ["agent_type"],
        unique=False,
    )
    op.create_index(
        "ix_political_agent_profiles_category",
        "political_agent_profiles",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_political_agent_profiles_category", table_name="political_agent_profiles")
    op.drop_index("ix_political_agent_profiles_agent_type", table_name="political_agent_profiles")
    op.drop_index("ix_political_agent_profiles_project_id", table_name="political_agent_profiles")
    op.drop_index("ix_political_agent_profiles_organization_id", table_name="political_agent_profiles")
    op.drop_table("political_agent_profiles")
