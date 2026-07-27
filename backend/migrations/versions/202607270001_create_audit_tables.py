"""crear tablas iniciales de auditoria

Revision ID: 202607270001
Revises:
Create Date: 2026-07-27 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607270001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("os_name", sa.String(length=128), nullable=False),
        sa.Column("agent_version", sa.String(length=64), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
    )

    op.create_table(
        "network_audit_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("os_name", sa.String(length=128), nullable=False),
        sa.Column("agent_version", sa.String(length=64), nullable=False),
        sa.Column("protocol", sa.String(length=32), nullable=False),
        sa.Column("local_ip", sa.String(length=45), nullable=True),
        sa.Column("public_ip", sa.String(length=45), nullable=True),
        sa.Column("destination_host", sa.String(length=255), nullable=True),
        sa.Column("destination_ip", sa.String(length=45), nullable=True),
        sa.Column("destination_port", sa.Integer(), nullable=True),
        sa.Column("http_method", sa.String(length=16), nullable=True),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("bytes_sent", sa.BigInteger(), nullable=False),
        sa.Column("bytes_received", sa.BigInteger(), nullable=False),
        sa.Column("network_interface", sa.String(length=128), nullable=True),
        sa.Column("mac_address", sa.String(length=32), nullable=True),
        sa.Column("request_metadata", sa.JSON(), nullable=False),
        sa.Column("response_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_network_audit_events_destination_host",
        "network_audit_events",
        ["destination_host"],
    )
    op.create_index(
        "ix_network_audit_events_destination_ip",
        "network_audit_events",
        ["destination_ip"],
    )
    op.create_index(
        "ix_network_audit_events_destination_port",
        "network_audit_events",
        ["destination_port"],
    )
    op.create_index("ix_network_audit_events_device_id", "network_audit_events", ["device_id"])
    op.create_index("ix_network_audit_events_local_ip", "network_audit_events", ["local_ip"])
    op.create_index("ix_network_audit_events_occurred_at", "network_audit_events", ["occurred_at"])
    op.create_index("ix_network_audit_events_protocol", "network_audit_events", ["protocol"])
    op.create_index("ix_network_audit_events_public_ip", "network_audit_events", ["public_ip"])

    op.create_table(
        "agent_lifecycle_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("agent_version", sa.String(length=64), nullable=False),
        sa.Column("local_ip", sa.String(length=45), nullable=True),
        sa.Column("public_ip", sa.String(length=45), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("downtime_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_agent_lifecycle_events_device_id",
        "agent_lifecycle_events",
        ["device_id"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_event_type",
        "agent_lifecycle_events",
        ["event_type"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_local_ip",
        "agent_lifecycle_events",
        ["local_ip"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_occurred_at",
        "agent_lifecycle_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_public_ip",
        "agent_lifecycle_events",
        ["public_ip"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_lifecycle_events_public_ip", table_name="agent_lifecycle_events")
    op.drop_index("ix_agent_lifecycle_events_occurred_at", table_name="agent_lifecycle_events")
    op.drop_index("ix_agent_lifecycle_events_local_ip", table_name="agent_lifecycle_events")
    op.drop_index("ix_agent_lifecycle_events_event_type", table_name="agent_lifecycle_events")
    op.drop_index("ix_agent_lifecycle_events_device_id", table_name="agent_lifecycle_events")
    op.drop_table("agent_lifecycle_events")

    op.drop_index("ix_network_audit_events_public_ip", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_protocol", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_occurred_at", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_local_ip", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_device_id", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_destination_port", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_destination_ip", table_name="network_audit_events")
    op.drop_index("ix_network_audit_events_destination_host", table_name="network_audit_events")
    op.drop_table("network_audit_events")

    op.drop_table("devices")
