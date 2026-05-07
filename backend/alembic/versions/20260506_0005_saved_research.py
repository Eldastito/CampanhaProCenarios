"""Add saved_research table; add delete/rename to graph_projects."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260506_0005"
down_revision: str = "20260504_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_research",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("candidate_name", sa.String(255), nullable=False),
        sa.Column("party", sa.String(255), nullable=False),
        sa.Column("party_abbreviation", sa.String(50), nullable=False),
        sa.Column("office", sa.String(100), nullable=False),
        sa.Column("search_performed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("political_history", sa.Text, nullable=True),
        sa.Column("current_mandates", sa.Text, nullable=True),
        sa.Column("platform_and_goals", sa.Text, nullable=True),
        sa.Column("recent_news", sa.Text, nullable=True),
        sa.Column("legal_issues", sa.Text, nullable=True),
        sa.Column("ficha_limpa_status", sa.String(255), nullable=True),
        sa.Column("background", sa.Text, nullable=True),
        sa.Column("rejection_profile", sa.JSON, nullable=True),
        sa.Column("graph_context_text", sa.Text, nullable=True),
        sa.Column("sources", sa.JSON, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_saved_research_org", "saved_research", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_research_org", "saved_research")
    op.drop_table("saved_research")
