"""political_projects.branding (header_logo_url, footer_logo_url, candidate_photo_url)

Revision ID: 20260510_0015
Revises: 20260510_0014
Create Date: 2026-05-10 23:00:00

Fase 5 do PRD v2 — relatórios exportáveis com branding por campanha.

Três colunas nullable em ``political_projects``. O mapper da Fase 2
preenche os valores quando o snapshot v1 trouxer ``campaign.details.headerLogo``,
``footerLogo`` ou ``candidatePhotoUrl``. Operador pode editar manualmente
via endpoint PATCH /political/projects/{id} (Fase 1 já permite update).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_0015"
down_revision: Union[str, None] = "20260510_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "political_projects",
        sa.Column("header_logo_url", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "political_projects",
        sa.Column("footer_logo_url", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "political_projects",
        sa.Column("candidate_photo_url", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("political_projects", "candidate_photo_url")
    op.drop_column("political_projects", "footer_logo_url")
    op.drop_column("political_projects", "header_logo_url")
