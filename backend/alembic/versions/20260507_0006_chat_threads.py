"""Add chat_threads and chat_messages tables."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260507_0006"
down_revision: str = "20260506_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("organization_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("graph_project_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_chat_threads_org", "chat_threads", ["organization_id"])
    op.create_index("ix_chat_threads_user", "chat_threads", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(64),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_chat_messages_thread", "chat_messages", ["thread_id"])
    op.create_index(
        "ix_chat_messages_thread_position",
        "chat_messages",
        ["thread_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_thread_position", "chat_messages")
    op.drop_index("ix_chat_messages_thread", "chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_user", "chat_threads")
    op.drop_index("ix_chat_threads_org", "chat_threads")
    op.drop_table("chat_threads")
