"""scenario_orchestrator_calls

Revision ID: 20260510_0016
Revises: 20260510_0015
Create Date: 2026-05-10 23:30:00

Fase 6 do PRD v2 — Claude Managed: orquestração de cenários a partir
de prompt em linguagem natural.

Cada chamada do endpoint /scenarios/generate persiste uma linha aqui
com prompt, agentes consultados, cenário criado e análises por agente.
Serve para:
- Rastreabilidade total (auditoria + reprodutibilidade).
- Rate limit por projeto (10 req/h conforme PRD).
- Histórico exposto no front quando útil.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0016"
down_revision: Union[str, None] = "20260510_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scenario_orchestrator_calls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("political_project_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("agents_consulted", sa.JSON(), nullable=False),
        sa.Column("scenario_id", sa.String(length=64), nullable=True),
        sa.Column("scenario_payload", sa.JSON(), nullable=False),
        sa.Column("agents_analyses", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("llm_model_used", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["political_project_id"], ["political_projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["scenarios.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenario_orchestrator_calls_organization_id",
        "scenario_orchestrator_calls",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenario_orchestrator_calls_political_project_id",
        "scenario_orchestrator_calls",
        ["political_project_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenario_orchestrator_calls_project_created",
        "scenario_orchestrator_calls",
        ["political_project_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scenario_orchestrator_calls_project_created",
        table_name="scenario_orchestrator_calls",
    )
    op.drop_index(
        "ix_scenario_orchestrator_calls_political_project_id",
        table_name="scenario_orchestrator_calls",
    )
    op.drop_index(
        "ix_scenario_orchestrator_calls_organization_id",
        table_name="scenario_orchestrator_calls",
    )
    op.drop_table("scenario_orchestrator_calls")
