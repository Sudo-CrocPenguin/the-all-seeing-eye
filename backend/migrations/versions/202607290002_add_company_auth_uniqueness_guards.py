"""agregar guardas de unicidad para auth multiempresa

Revision ID: 202607290002
Revises: 202607290001
Create Date: 2026-07-29 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607290002"
down_revision: str | None = "202607290001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_company_enrollment_requests_pending_device",
        "company_enrollment_requests",
        ["company_id", "device_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "uq_company_device_links_active_device",
        "company_device_links",
        ["company_id", "device_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE' AND revoked_at IS NULL"),
        sqlite_where=sa.text("status = 'ACTIVE' AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_company_device_links_active_device",
        table_name="company_device_links",
    )
    op.drop_index(
        "uq_company_enrollment_requests_pending_device",
        table_name="company_enrollment_requests",
    )
