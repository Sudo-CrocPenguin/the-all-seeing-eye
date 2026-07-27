from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from agent.app.config import AgentSettings
from agent.app.device_identity import (
    DeviceIdentity,
    DeviceIdentityCollector,
    NetworkInterface,
    _machine_fingerprint,
)
from agent.app.network_collector import NetworkConnectionCollector, ObservedNetworkConnection
from agent.app.runner import AgentRunner


def test_agent_settings_from_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://backend.local:8000/")
    monkeypatch.setenv("AGENT_DEVICE_ID", "device-123")
    monkeypatch.setenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("AGENT_SCAN_INTERVAL_SECONDS", "5")

    settings = AgentSettings.from_environment()

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-123"
    assert settings.heartbeat_interval_seconds == 30
    assert settings.scan_interval_seconds == 5


def test_device_identity_uses_configured_id_and_handles_interface_permission(
    monkeypatch: Any,
) -> None:
    def raise_permission_error() -> dict[str, object]:
        raise PermissionError("sin permiso")

    monkeypatch.setattr("agent.app.device_identity.psutil.net_if_addrs", raise_permission_error)

    identity = DeviceIdentityCollector(AgentSettings(device_id="device-fixed")).collect()

    assert identity.device_id == "device-fixed"
    assert identity.interfaces == ()


def test_machine_fingerprint_has_fallback_value() -> None:
    assert _machine_fingerprint()


def test_network_collector_builds_connection_payload(monkeypatch: Any) -> None:
    raw_connection = SimpleNamespace(
        type=1,
        laddr=SimpleNamespace(ip="192.168.1.10", port=51515),
        raddr=SimpleNamespace(ip="93.184.216.34", port=443),
        status="ESTABLISHED",
    )
    monkeypatch.setattr(
        "agent.app.network_collector.psutil.net_connections",
        lambda kind: [raw_connection],
    )
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(
            NetworkInterface(
                name="eth0",
                local_ip="192.168.1.10",
                mac_address="00:11:22:33:44:55",
                is_up=True,
            ),
        ),
    )

    connections = NetworkConnectionCollector().collect(identity)

    assert len(connections) == 1
    payload = connections[0].to_backend_payload(identity)
    assert payload["device_id"] == "device-1"
    assert payload["protocol"] == "TCP"
    assert payload["destination_ip"] == "93.184.216.34"
    assert payload["destination_port"] == 443
    assert payload["network_interface"] == "eth0"
    assert payload["mac_address"] == "00:11:22:33:44:55"


def test_runner_once_reports_lifecycle_and_network_event() -> None:
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(),
    )
    connection = ObservedNetworkConnection(
        occurred_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
        protocol="TCP",
        local_ip="192.168.1.10",
        local_port=51515,
        destination_ip="93.184.216.34",
        destination_port=443,
        status="ESTABLISHED",
        network_interface="eth0",
        mac_address="00:11:22:33:44:55",
    )
    api_client = FakeAuditApiClient()
    runner = AgentRunner(
        AgentSettings(heartbeat_interval_seconds=1, scan_interval_seconds=1),
        identity_collector=FakeIdentityCollector(identity),
        network_collector=FakeNetworkCollector([connection]),
        api_client=api_client,
    )

    runner.run_once()

    assert api_client.registered_devices == ["device-1"]
    assert api_client.lifecycle_events == [
        "AGENT_STARTED",
        "AGENT_HEARTBEAT",
        "AGENT_STOPPING",
        "AGENT_STOPPED",
    ]
    assert len(api_client.network_events) == 1
    assert api_client.network_events[0]["destination_ip"] == "93.184.216.34"


class FakeIdentityCollector:
    def __init__(self, identity: DeviceIdentity) -> None:
        self._identity = identity

    def collect(self) -> DeviceIdentity:
        return self._identity


class FakeNetworkCollector:
    def __init__(self, connections: list[ObservedNetworkConnection]) -> None:
        self._connections = connections

    def collect(self, _identity: DeviceIdentity) -> list[ObservedNetworkConnection]:
        return self._connections


class FakeAuditApiClient:
    def __init__(self) -> None:
        self.registered_devices: list[str] = []
        self.lifecycle_events: list[str] = []
        self.network_events: list[dict[str, object]] = []

    def register_device(self, identity: DeviceIdentity) -> dict[str, object]:
        self.registered_devices.append(identity.device_id)
        return {}

    def send_lifecycle_event(
        self,
        _identity: DeviceIdentity,
        event_type: str,
        _occurred_at: str,
        *,
        reason: str | None = None,
    ) -> dict[str, object]:
        self.lifecycle_events.append(event_type)
        return {"reason": reason or ""}

    def send_network_event(self, payload: dict[str, object]) -> dict[str, object]:
        self.network_events.append(payload)
        return {}
