"""crear vista unificada de movimientos por dispositivo

Revision ID: 202607280002
Revises: 202607280001
Create Date: 2026-07-28 00:02:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202607280002"
down_revision: str | None = "202607280001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS device_movements")
    op.execute(_device_movements_view_sql())


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS device_movements")


def _device_movements_view_sql() -> str:
    connection_status = _connection_status_expression()
    return f"""
CREATE VIEW device_movements AS
SELECT
    event_id,
    occurred_at,
    created_at,
    'NETWORK_CONNECTION' AS movement_type,
    device_id,
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
    device_id,
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
