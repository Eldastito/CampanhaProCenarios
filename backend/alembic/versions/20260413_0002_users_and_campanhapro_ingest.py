"""add users, campanhapro_events, campanhapro_snapshots

Revision ID: 20260413_0002
Revises: 20260409_0001
Create Date: 2026-04-13 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260413_0002"
down_revision: Union[str, None] = "20260409_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_organization_id", "users", ["organization_id"], unique=False)

    # ------------------------------------------------------------------
    # campanhapro_events
    # ------------------------------------------------------------------
    op.create_table(
        "campanhapro_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("payload_version", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_campanhapro_events_request_id", "campanhapro_events", ["request_id"], unique=True)
    op.create_index("ix_campanhapro_events_organization_id", "campanhapro_events", ["organization_id"], unique=False)
    op.create_index("ix_campanhapro_events_event_type", "campanhapro_events", ["event_type"], unique=False)

    # ------------------------------------------------------------------
    # campanhapro_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "campanhapro_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=100), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_type", sa.String(length=100), nullable=False),
        sa.Column("reference_date", sa.DateTime(), nullable=False),
        sa.Column("payload_version", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_campanhapro_snapshots_request_id", "campanhapro_snapshots", ["request_id"], unique=True)
    op.create_index("ix_campanhapro_snapshots_organization_id", "campanhapro_snapshots", ["organization_id"], unique=False)
    op.create_index("ix_campanhapro_snapshots_snapshot_type", "campanhapro_snapshots", ["snapshot_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_campanhapro_snapshots_snapshot_type", table_name="campanhapro_snapshots")
    op.drop_index("ix_campanhapro_snapshots_organization_id", table_name="campanhapro_snapshots")
    op.drop_index("ix_campanhapro_snapshots_request_id", table_name="campanhapro_snapshots")
    op.drop_table("campanhapro_snapshots")

    op.drop_index("ix_campanhapro_events_event_type", table_name="campanhapro_events")
    op.drop_index("ix_campanhapro_events_organization_id", table_name="campanhapro_events")
    op.drop_index("ix_campanhapro_events_request_id", table_name="campanhapro_events")
    op.drop_table("campanhapro_events")

    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
