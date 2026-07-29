"""agregar contexto de empresa a eventos de auditoria

Revision ID: 202607290003
Revises: 202607290002
Create Date: 2026-07-29 00:03:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607290003"
down_revision: str | None = "202607290002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS device_movements")
    op.add_column(
        "network_audit_events",
        sa.Column("company_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "network_audit_events",
        sa.Column("company_device_link_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "agent_lifecycle_events",
        sa.Column("company_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "agent_lifecycle_events",
        sa.Column("company_device_link_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_network_audit_events_company_id", "network_audit_events", ["company_id"])
    op.create_index(
        "ix_network_audit_events_company_device_link_id",
        "network_audit_events",
        ["company_device_link_id"],
    )
    op.create_index(
        "ix_network_audit_events_company_device_occurred",
        "network_audit_events",
        ["company_id", "device_id", "occurred_at"],
    )
    op.create_index(
        "ix_network_audit_events_company_link_occurred",
        "network_audit_events",
        ["company_id", "company_device_link_id", "occurred_at"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_company_id",
        "agent_lifecycle_events",
        ["company_id"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_company_device_link_id",
        "agent_lifecycle_events",
        ["company_device_link_id"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_company_device_occurred",
        "agent_lifecycle_events",
        ["company_id", "device_id", "occurred_at"],
    )
    op.create_index(
        "ix_agent_lifecycle_events_company_link_occurred",
        "agent_lifecycle_events",
        ["company_id", "company_device_link_id", "occurred_at"],
    )
    op.execute(_device_movements_view_sql(include_company_context=True))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS device_movements")
    op.drop_index(
        "ix_agent_lifecycle_events_company_link_occurred",
        table_name="agent_lifecycle_events",
    )
    op.drop_index(
        "ix_agent_lifecycle_events_company_device_occurred",
        table_name="agent_lifecycle_events",
    )
    op.drop_index(
        "ix_agent_lifecycle_events_company_device_link_id",
        table_name="agent_lifecycle_events",
    )
    op.drop_index("ix_agent_lifecycle_events_company_id", table_name="agent_lifecycle_events")
    op.drop_index(
        "ix_network_audit_events_company_link_occurred",
        table_name="network_audit_events",
    )
    op.drop_index(
        "ix_network_audit_events_company_device_occurred",
        table_name="network_audit_events",
    )
    op.drop_index(
        "ix_network_audit_events_company_device_link_id",
        table_name="network_audit_events",
    )
    op.drop_index("ix_network_audit_events_company_id", table_name="network_audit_events")
    op.drop_column("agent_lifecycle_events", "company_device_link_id")
    op.drop_column("agent_lifecycle_events", "company_id")
    op.drop_column("network_audit_events", "company_device_link_id")
    op.drop_column("network_audit_events", "company_id")
    op.execute(_device_movements_view_sql(include_company_context=False))


def _device_movements_view_sql(*, include_company_context: bool) -> str:
    connection_status = _connection_status_expression()
    network_company_columns = ""
    lifecycle_company_columns = ""
    if include_company_context:
        network_company_columns = """
    company_id,
    company_device_link_id,"""
        lifecycle_company_columns = """
    company_id,
    company_device_link_id,"""

    return f"""
CREATE VIEW device_movements AS
SELECT
    event_id,
    occurred_at,
    created_at,
    'NETWORK_CONNECTION' AS movement_type,
    device_id,{network_company_columns}
    hostname,
    local_ip,
    public_ip,
    COALESCE(service_name, destination_host, destination_ip, 'Conexion saliente') AS summary,
    protocol,
    destination_host,
    destination_ip,
    destination_port,
    local_username,
    process_id,
    process_name,
    process_executable,
    service_name,
    network_interface,
    {connection_status} AS connection_status,
    NULL AS lifecycle_reason
FROM network_audit_events
UNION ALL
SELECT
    event_id,
    occurred_at,
    created_at,
    event_type AS movement_type,
    device_id,{lifecycle_company_columns}
    hostname,
    local_ip,
    public_ip,
    CASE
        WHEN reason IS NULL THEN event_type
        ELSE event_type || ': ' || reason
    END AS summary,
    NULL AS protocol,
    NULL AS destination_host,
    NULL AS destination_ip,
    NULL AS destination_port,
    NULL AS local_username,
    NULL AS process_id,
    NULL AS process_name,
    NULL AS process_executable,
    NULL AS service_name,
    NULL AS network_interface,
    NULL AS connection_status,
    reason AS lifecycle_reason
FROM agent_lifecycle_events
"""


def _connection_status_expression() -> str:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        return "request_metadata ->> 'connection_status'"
    return "json_extract(request_metadata, '$.connection_status')"
