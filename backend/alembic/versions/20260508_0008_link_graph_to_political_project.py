"""link graph_projects to political_projects

Revision ID: 20260508_0008
Revises: 20260508_0007
Create Date: 2026-05-08 12:00:00

Adiciona coluna nullable political_project_id em graph_projects, ligando
um grafo de conhecimento a um projeto eleitoral (Fase 3 — Grafo Político).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0008"
down_revision: Union[str, None] = "20260508_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "graph_projects",
        sa.Column("political_project_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_graph_projects_political_project_id",
        "graph_projects",
        ["political_project_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_graph_projects_political_project_id",
        "graph_projects",
        "political_projects",
        ["political_project_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_graph_projects_political_project_id",
        "graph_projects",
        type_="foreignkey",
    )
    op.drop_index("ix_graph_projects_political_project_id", table_name="graph_projects")
    op.drop_column("graph_projects", "political_project_id")
