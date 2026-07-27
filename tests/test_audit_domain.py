from datetime import UTC, datetime

import pytest

from backend.app.audit.domain.entities import (
    AgentLifecycleEvent,
    AgentLifecycleEventType,
    NetworkAuditEvent,
)
from backend.app.shared.domain import DomainValidationError


def test_network_event_normalizes_protocol_and_http_method() -> None:
    event = NetworkAuditEvent(
        event_id="event-1",
        occurred_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="linux",
        agent_version="0.1.0",
        protocol="https",
        http_method="get",
        local_ip="192.168.1.10",
        public_ip="203.0.113.10",
        destination_ip="93.184.216.34",
        destination_port=443,
        bytes_sent=512,
        bytes_received=2048,
    )

    assert event.protocol == "HTTPS"
    assert event.http_method == "GET"


def test_network_event_rejects_invalid_ip() -> None:
    with pytest.raises(DomainValidationError, match="local_ip no es una IP valida"):
        NetworkAuditEvent(
            event_id="event-1",
            occurred_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
            device_id="device-1",
            hostname="DEV-LAPTOP-001",
            os_name="linux",
            agent_version="0.1.0",
            protocol="tcp",
            local_ip="no-es-ip",
        )


def test_network_event_rejects_negative_bytes() -> None:
    with pytest.raises(DomainValidationError, match="bytes_sent no puede ser negativo"):
        NetworkAuditEvent(
            event_id="event-1",
            occurred_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
            device_id="device-1",
            hostname="DEV-LAPTOP-001",
            os_name="linux",
            agent_version="0.1.0",
            protocol="tcp",
            bytes_sent=-1,
        )


def test_lifecycle_event_accepts_missed_heartbeat_data() -> None:
    event = AgentLifecycleEvent(
        event_id="event-2",
        event_type=AgentLifecycleEventType.MISSED_HEARTBEAT,
        occurred_at=datetime(2026, 7, 27, 14, 3, tzinfo=UTC),
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        agent_version="0.1.0",
        local_ip="192.168.1.10",
        public_ip="203.0.113.10",
        last_seen_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
        detected_at=datetime(2026, 7, 27, 14, 3, tzinfo=UTC),
        downtime_seconds=180,
    )

    assert event.event_type == AgentLifecycleEventType.MISSED_HEARTBEAT
    assert event.downtime_seconds == 180

