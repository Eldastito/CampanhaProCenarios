"""campanhapro_snapshots.campaign_id + schema_version

Revision ID: 20260510_0011
Revises: 20260510_0010
Create Date: 2026-05-10 12:00:00

Fase 1 do PRD v2: anota cada snapshot com a campanha de origem
(``campaign_id``) e a versão do contrato (``schema_version``).

Estratégia para preservar registros legados:
- Ambas as colunas são adicionadas como nullable.
- Snapshots legados (formato v0 sem ``schemaVersion``) ficam com NULL —
  a Fase 2 ignora esses registros no mapper por falta de campaign_id.
- Snapshots v1 sempre populam as duas colunas.

Índice composto ``(organization_id, campaign_id, reference_date)``
suporta a query do mapper "último snapshot v1 da campanha X".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0011"
down_revision: Union[str, None] = "20260510_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campanhapro_snapshots",
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "campanhapro_snapshots",
        sa.Column("schema_version", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_campanhapro_snapshots_campaign_id",
        "campanhapro_snapshots",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_campanhapro_snapshots_org_campaign_ref",
        "campanhapro_snapshots",
        ["organization_id", "campaign_id", "reference_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campanhapro_snapshots_org_campaign_ref",
        table_name="campanhapro_snapshots",
    )
    op.drop_index(
        "ix_campanhapro_snapshots_campaign_id",
        table_name="campanhapro_snapshots",
    )
    op.drop_column("campanhapro_snapshots", "schema_version")
    op.drop_column("campanhapro_snapshots", "campaign_id")
