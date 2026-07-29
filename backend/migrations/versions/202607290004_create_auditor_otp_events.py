"""crear eventos de auditor otp

Revision ID: 202607290004
Revises: 202607290003
Create Date: 2026-07-29 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607290004"
down_revision: str | None = "202607290003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auditor_otp_events",
        sa.Column("otp_event_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("auditor_access_request_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("otp_event_id"),
    )
    op.create_index("ix_auditor_otp_events_company_id", "auditor_otp_events", ["company_id"])
    op.create_index("ix_auditor_otp_events_device_id", "auditor_otp_events", ["device_id"])
    op.create_index("ix_auditor_otp_events_client_ip", "auditor_otp_events", ["client_ip"])
    op.create_index(
        "ix_auditor_otp_events_auditor_access_request_id",
        "auditor_otp_events",
        ["auditor_access_request_id"],
    )
    op.create_index("ix_auditor_otp_events_event_type", "auditor_otp_events", ["event_type"])
    op.create_index(
        "ix_auditor_otp_events_company_type_occurred",
        "auditor_otp_events",
        ["company_id", "event_type", "occurred_at"],
    )
    op.create_index(
        "ix_auditor_otp_events_device_type_occurred",
        "auditor_otp_events",
        ["device_id", "event_type", "occurred_at"],
    )
    op.create_index(
        "ix_auditor_otp_events_ip_type_occurred",
        "auditor_otp_events",
        ["client_ip", "event_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auditor_otp_events_ip_type_occurred", table_name="auditor_otp_events")
    op.drop_index("ix_auditor_otp_events_device_type_occurred", table_name="auditor_otp_events")
    op.drop_index("ix_auditor_otp_events_company_type_occurred", table_name="auditor_otp_events")
    op.drop_index("ix_auditor_otp_events_event_type", table_name="auditor_otp_events")
    op.drop_index(
        "ix_auditor_otp_events_auditor_access_request_id",
        table_name="auditor_otp_events",
    )
    op.drop_index("ix_auditor_otp_events_client_ip", table_name="auditor_otp_events")
    op.drop_index("ix_auditor_otp_events_device_id", table_name="auditor_otp_events")
    op.drop_index("ix_auditor_otp_events_company_id", table_name="auditor_otp_events")
    op.drop_table("auditor_otp_events")
