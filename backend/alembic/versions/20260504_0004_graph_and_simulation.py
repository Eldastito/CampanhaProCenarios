"""add graph, simulation and saved_predictions tables

Revision ID: 20260504_0004
Revises: 20260504_0003
Create Date: 2026-05-04 12:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_0004"
down_revision: Union[str, None] = "20260504_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_projects",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scenario_type", sa.String(32), nullable=False, server_default="political"),
        sa.Column("ontology", sa.JSON, nullable=False),
        sa.Column("source_text", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("node_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("edge_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_graph_projects_org", "graph_projects", ["organization_id"])

    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("graph_projects.id"), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("properties", sa.JSON, nullable=False),
    )
    op.create_index("ix_graph_nodes_project", "graph_nodes", ["project_id"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("graph_projects.id"), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("graph_nodes.id"), nullable=False),
        sa.Column("target_id", sa.String(64), sa.ForeignKey("graph_nodes.id"), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("properties", sa.JSON, nullable=False),
    )
    op.create_index("ix_graph_edges_project", "graph_edges", ["project_id"])

    op.create_table(
        "simulations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("graph_projects.id"), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("step_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_simulations_org", "simulations", ["organization_id"])
    op.create_index("ix_simulations_project", "simulations", ["project_id"])

    op.create_table(
        "simulation_steps",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("simulation_id", sa.String(64), sa.ForeignKey("simulations.id"), nullable=False),
        sa.Column("step_number", sa.Integer, nullable=False),
        sa.Column("agent_label", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(100), nullable=False),
        sa.Column("agent_node_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(50), nullable=False, server_default="speak"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("affected_nodes", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_simulation_steps_sim", "simulation_steps", ["simulation_id"])

    op.create_table(
        "saved_predictions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prediction_type", sa.String(50), nullable=False),
        sa.Column("scenario_type", sa.String(32), nullable=False, server_default="education"),
        sa.Column("factors", sa.JSON, nullable=False),
        sa.Column("result_value", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("explanation", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_saved_predictions_org", "saved_predictions", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_predictions_org", "saved_predictions")
    op.drop_table("saved_predictions")
    op.drop_index("ix_simulation_steps_sim", "simulation_steps")
    op.drop_table("simulation_steps")
    op.drop_index("ix_simulations_project", "simulations")
    op.drop_index("ix_simulations_org", "simulations")
    op.drop_table("simulations")
    op.drop_index("ix_graph_edges_project", "graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("ix_graph_nodes_project", "graph_nodes")
    op.drop_table("graph_nodes")
    op.drop_index("ix_graph_projects_org", "graph_projects")
    op.drop_table("graph_projects")
