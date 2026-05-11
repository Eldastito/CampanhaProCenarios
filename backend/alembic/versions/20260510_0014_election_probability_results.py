"""election_probability_results

Revision ID: 20260510_0014
Revises: 20260510_0013
Create Date: 2026-05-10 22:00:00

Fase 4 do PRD v2 — resultados do Monte Carlo de probabilidade de eleição.

Cada linha representa **uma simulação completa** de uma disputa entre N
candidatos. ``status`` rastreia o ciclo do worker; ``input_candidates`` e
``output_results`` guardam o que entrou e saiu para reprodutibilidade,
junto com ``seed`` e ``iterations``.

Índice composto ``(organization_id, political_project_id, created_at)``
para a query "histórico do projeto".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0014"
down_revision: Union[str, None] = "20260510_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "election_probability_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("political_project_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("office", sa.String(length=100), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_candidates", sa.JSON(), nullable=False),
        sa.Column("output_results", sa.JSON(), nullable=False),
        sa.Column("confidence_level", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["political_project_id"], ["political_projects.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_election_probability_results_organization_id",
        "election_probability_results",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_election_probability_results_political_project_id",
        "election_probability_results",
        ["political_project_id"],
        unique=False,
    )
    op.create_index(
        "ix_election_probability_results_org_project_created",
        "election_probability_results",
        ["organization_id", "political_project_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_election_probability_results_org_project_created",
        table_name="election_probability_results",
    )
    op.drop_index(
        "ix_election_probability_results_political_project_id",
        table_name="election_probability_results",
    )
    op.drop_index(
        "ix_election_probability_results_organization_id",
        table_name="election_probability_results",
    )
    op.drop_table("election_probability_results")
