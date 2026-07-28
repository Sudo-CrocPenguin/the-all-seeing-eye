"""enriquecer eventos de red para evidencia forense

Revision ID: 202607280001
Revises: 202607270002
Create Date: 2026-07-28 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607280001"
down_revision: str | None = "202607270002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "network_audit_events",
        sa.Column("local_username", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "network_audit_events",
        sa.Column("process_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "network_audit_events",
        sa.Column("process_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "network_audit_events",
        sa.Column("process_executable", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "network_audit_events",
        sa.Column("service_name", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_network_audit_events_local_username",
        "network_audit_events",
        ["local_username"],
    )
    op.create_index(
        "ix_network_audit_events_process_name",
        "network_audit_events",
        ["process_name"],
    )
    op.create_index(
        "ix_network_audit_events_service_name",
        "network_audit_events",
        ["service_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_network_audit_events_service_name", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_process_name", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_local_username", table_name="network_audit_events")
    op.drop_column("network_audit_events", "service_name")
    op.drop_column("network_audit_events", "process_executable")
    op.drop_column("network_audit_events", "process_name")
    op.drop_column("network_audit_events", "process_id")
    op.drop_column("network_audit_events", "local_username")
