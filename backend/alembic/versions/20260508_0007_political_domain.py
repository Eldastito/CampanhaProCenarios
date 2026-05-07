"""political domain: projects, evidence sources, compliance alerts, audit logs

Revision ID: 20260508_0007
Revises: 20260507_0006
Create Date: 2026-05-08 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0007"
down_revision: Union[str, None] = "20260507_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # political_projects
    # ------------------------------------------------------------------
    op.create_table(
        "political_projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("election_year", sa.Integer(), nullable=False),
        sa.Column("office", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("municipality", sa.String(length=255), nullable=True),
        sa.Column("candidate_name", sa.String(length=255), nullable=False),
        sa.Column("parties", sa.JSON(), nullable=False),
        sa.Column("known_opponents", sa.JSON(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("horizon_start", sa.DateTime(), nullable=True),
        sa.Column("horizon_end", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_political_projects_organization_id",
        "political_projects",
        ["organization_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # political_evidence_sources
    # ------------------------------------------------------------------
    op.create_table(
        "political_evidence_sources",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("reliability_level", sa.String(length=50), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("storage_uri", sa.String(length=1000), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["political_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_political_evidence_sources_organization_id",
        "political_evidence_sources",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_evidence_sources_project_id",
        "political_evidence_sources",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_evidence_sources_content_hash",
        "political_evidence_sources",
        ["content_hash"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # political_compliance_alerts
    # ------------------------------------------------------------------
    op.create_table(
        "political_compliance_alerts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("alert_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", sa.String(length=64), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["political_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_political_compliance_alerts_organization_id",
        "political_compliance_alerts",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_compliance_alerts_project_id",
        "political_compliance_alerts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_compliance_alerts_alert_type",
        "political_compliance_alerts",
        ["alert_type"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # political_audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "political_audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("actor_user_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["political_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_political_audit_logs_organization_id",
        "political_audit_logs",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_audit_logs_project_id",
        "political_audit_logs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_audit_logs_actor_user_id",
        "political_audit_logs",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_political_audit_logs_action",
        "political_audit_logs",
        ["action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_political_audit_logs_action", table_name="political_audit_logs")
    op.drop_index("ix_political_audit_logs_actor_user_id", table_name="political_audit_logs")
    op.drop_index("ix_political_audit_logs_project_id", table_name="political_audit_logs")
    op.drop_index("ix_political_audit_logs_organization_id", table_name="political_audit_logs")
    op.drop_table("political_audit_logs")

    op.drop_index("ix_political_compliance_alerts_alert_type", table_name="political_compliance_alerts")
    op.drop_index("ix_political_compliance_alerts_project_id", table_name="political_compliance_alerts")
    op.drop_index("ix_political_compliance_alerts_organization_id", table_name="political_compliance_alerts")
    op.drop_table("political_compliance_alerts")

    op.drop_index("ix_political_evidence_sources_content_hash", table_name="political_evidence_sources")
    op.drop_index("ix_political_evidence_sources_project_id", table_name="political_evidence_sources")
    op.drop_index("ix_political_evidence_sources_organization_id", table_name="political_evidence_sources")
    op.drop_table("political_evidence_sources")

    op.drop_index("ix_political_projects_organization_id", table_name="political_projects")
    op.drop_table("political_projects")
