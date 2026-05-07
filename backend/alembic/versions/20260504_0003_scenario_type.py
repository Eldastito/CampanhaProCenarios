"""add scenario_type to scenarios

Revision ID: 20260504_0003
Revises: 20260413_0002
Create Date: 2026-05-04 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_0003"
down_revision: Union[str, None] = "20260413_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scenarios",
        sa.Column(
            "scenario_type",
            sa.String(length=32),
            nullable=False,
            server_default="education",
        ),
    )


def downgrade() -> None:
    op.drop_column("scenarios", "scenario_type")
