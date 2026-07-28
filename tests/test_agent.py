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
from agent.app.env_file import parse_environment_lines
from agent.app.local_queue import LocalAgentRequestQueue, QueuedAuditApiClient, QueuedRequest
from agent.app.network_collector import NetworkConnectionCollector, ObservedNetworkConnection
from agent.app.runner import AgentConfigurationError, AgentRunner
from agent.app.service_map import ServiceMap, ServiceMapEntry
from agent.app.transport import AgentTransportError, AuditApiClient
from agent.app.windows_service import (
    WINDOWS_SERVICE_DESCRIPTION,
    WINDOWS_SERVICE_DISPLAY_NAME,
    WINDOWS_SERVICE_NAME,
    load_pywin32_modules,
)


def test_agent_settings_from_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://backend.local:8000/")
    monkeypatch.setenv("AGENT_DEVICE_ID", "device-123")
    monkeypatch.setenv("AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AGENT_TOKEN_HEADER", "X-Custom-Agent-Token")
    monkeypatch.setenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("AGENT_SCAN_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("AGENT_REQUEST_RETRY_BACKOFF_SECONDS", "7")
    monkeypatch.setenv("AGENT_QUEUE_FILE", "/tmp/the-all-seeing-eye-agent-queue.jsonl")
    monkeypatch.setenv("AGENT_SERVICE_MAP_FILE", "/tmp/the-all-seeing-eye-service-map.json")

    settings = AgentSettings.from_environment()

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-123"
    assert settings.agent_token == "agent-token"
    assert settings.agent_token_header == "X-Custom-Agent-Token"
    assert settings.heartbeat_interval_seconds == 30
    assert settings.scan_interval_seconds == 5
    assert settings.request_retry_backoff_seconds == 7
    assert str(settings.queue_file) == "/tmp/the-all-seeing-eye-agent-queue.jsonl"
    assert str(settings.service_map_file) == "/tmp/the-all-seeing-eye-service-map.json"


def test_agent_settings_from_env_file(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.delenv("AGENT_BACKEND_URL", raising=False)
    monkeypatch.delenv("AGENT_DEVICE_ID", raising=False)
    monkeypatch.delenv("AGENT_TOKEN", raising=False)
    env_file = tmp_path / "agent.env"
    env_file.write_text(
        "\n".join(
            [
                "AGENT_BACKEND_URL=http://backend.local:8000/",
                "AGENT_DEVICE_ID=device-file",
                "AGENT_TOKEN=token-file",
                "AGENT_HEARTBEAT_INTERVAL_SECONDS=20",
            ],
        ),
        encoding="utf-8",
    )

    settings = AgentSettings.from_environment(env_file)

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-file"
    assert settings.agent_token == "token-file"
    assert settings.heartbeat_interval_seconds == 20


def test_environment_variables_override_env_file(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://env.local:8000")
    env_file = tmp_path / "agent.env"
    env_file.write_text("AGENT_BACKEND_URL=http://file.local:8000\n", encoding="utf-8")

    settings = AgentSettings.from_environment(env_file)

    assert settings.backend_url == "http://env.local:8000"


def test_parse_environment_lines_rejects_invalid_variable() -> None:
    try:
        parse_environment_lines(["AGENT TOKEN=invalid"])
    except ValueError as exc:
        assert "variable invalida" in str(exc)
    else:
        raise AssertionError("El archivo env debe rechazar nombres invalidos")


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
        pid=1234,
    )
    monkeypatch.setattr(
        "agent.app.network_collector.psutil.net_connections",
        lambda kind: [raw_connection],
    )
    monkeypatch.setattr("agent.app.network_collector.psutil.Process", FakeProcess)
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

    service_map = ServiceMap(
        [
            ServiceMapEntry(
                name="Servicio HTTPS de ejemplo",
                destination_ip="93.184.216.34",
                destination_port=443,
                destination_host="example.com",
            ),
        ],
    )
    connections = NetworkConnectionCollector(service_map).collect(identity)

    assert len(connections) == 1
    payload = connections[0].to_backend_payload(identity)
    assert payload["device_id"] == "device-1"
    assert payload["protocol"] == "TCP"
    assert payload["destination_ip"] == "93.184.216.34"
    assert payload["destination_host"] == "example.com"
    assert payload["destination_port"] == 443
    assert payload["network_interface"] == "eth0"
    assert payload["mac_address"] == "00:11:22:33:44:55"
    assert payload["local_username"] == "dev-user"
    assert payload["process_id"] == 1234
    assert payload["process_name"] == "psql"
    assert payload["process_executable"] == "/usr/bin/psql"
    assert payload["service_name"] == "Servicio HTTPS de ejemplo"


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


def test_runner_forever_uses_scan_interval_independently_from_heartbeat() -> None:
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
    clock = FakeMonotonicClock()
    stop_signal = FakeStopSignal(clock, stop_after_waits=4)
    runner = SignalFreeAgentRunner(
        AgentSettings(
            heartbeat_interval_seconds=10,
            scan_interval_seconds=3,
            network_event_dedup_seconds=0,
        ),
        identity_collector=FakeIdentityCollector(identity),
        network_collector=FakeNetworkCollector([connection]),
        api_client=api_client,
        stop_signal=stop_signal,
        monotonic_clock=clock,
    )

    runner.run_forever()

    assert api_client.lifecycle_events == [
        "AGENT_STARTED",
        "AGENT_STOPPING",
        "AGENT_STOPPED",
    ]
    assert len(api_client.network_events) == 3
    assert stop_signal.waits == [3.0, 3.0, 3.0, 1.0]


def test_runner_requires_agent_token_when_using_real_client() -> None:
    try:
        AgentRunner(AgentSettings())
    except AgentConfigurationError as exc:
        assert "AGENT_TOKEN" in str(exc)
    else:
        raise AssertionError("AgentRunner debe exigir AGENT_TOKEN")


def test_api_client_sends_agent_token_header(monkeypatch: Any) -> None:
    captured_headers: dict[str, str] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"{}"

    def fake_urlopen(request: Any, timeout: int) -> FakeResponse:
        assert timeout == 10
        captured_headers.update(dict(request.header_items()))
        return FakeResponse()

    monkeypatch.setattr("agent.app.transport.urlopen", fake_urlopen)
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(),
    )
    client = AuditApiClient(
        "http://backend.local:8000",
        agent_token="agent-token",
        agent_token_header="X-Agent-Token",
    )

    client.register_device(identity)

    assert captured_headers["X-agent-token"] == "agent-token"


def test_queued_client_persists_request_when_backend_fails(tmp_path: Any) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    client = QueuedAuditApiClient(
        FailingPostJsonClient(),
        LocalAgentRequestQueue(queue_file),
        retry_backoff_seconds=30,
    )

    response = client.send_network_event(
        {
            "device_id": "device-1",
            "hostname": "DEV-LAPTOP-001",
            "os_name": "Linux",
            "agent_version": "0.1.0",
            "occurred_at": "2026-07-27T14:00:00+00:00",
            "protocol": "TCP",
        },
    )

    assert response == {}
    queued_requests = LocalAgentRequestQueue(queue_file).read_all()
    assert len(queued_requests) == 1
    assert queued_requests[0].path == "/api/v1/audit/network-events"
    assert queued_requests[0].payload["device_id"] == "device-1"


def test_queued_client_flushes_pending_requests_before_new_send(tmp_path: Any) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    queue = LocalAgentRequestQueue(queue_file)
    queue.enqueue(
        QueuedRequest(
            path="/api/v1/audit/lifecycle-events",
            payload={"event_type": "AGENT_HEARTBEAT"},
        ),
    )
    post_client = RecordingPostJsonClient()
    client = QueuedAuditApiClient(post_client, queue, retry_backoff_seconds=30)

    response = client.send_network_event(
        {
            "device_id": "device-1",
            "hostname": "DEV-LAPTOP-001",
            "os_name": "Linux",
            "agent_version": "0.1.0",
            "occurred_at": "2026-07-27T14:00:00+00:00",
            "protocol": "TCP",
        },
    )

    assert response == {"status": "ok"}
    assert [request[0] for request in post_client.requests] == [
        "/api/v1/audit/lifecycle-events",
        "/api/v1/audit/network-events",
    ]
    assert queue.read_all() == []


def test_windows_service_metadata_is_corporate_and_visible() -> None:
    assert WINDOWS_SERVICE_NAME == "AllSeeingEyeAgent"
    assert WINDOWS_SERVICE_DISPLAY_NAME == "The All Seeing Eye Agent"
    assert "corporativo autorizado" in WINDOWS_SERVICE_DESCRIPTION


def test_windows_service_reports_missing_pywin32(monkeypatch: Any) -> None:
    def raise_import_error(_name: str) -> object:
        raise ImportError("missing")

    monkeypatch.setattr("agent.app.windows_service.importlib.import_module", raise_import_error)

    try:
        load_pywin32_modules()
    except RuntimeError as exc:
        assert "pywin32" in str(exc)
    else:
        raise AssertionError("El servicio Windows debe explicar que falta pywin32")


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


class FailingPostJsonClient:
    def post_json(self, _path: str, _payload: dict[str, object]) -> dict[str, object]:
        raise AgentTransportError("backend no disponible")


class RecordingPostJsonClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append((path, payload))
        return {"status": "ok"}


class FakeProcess:
    def __init__(self, process_id: int) -> None:
        self._process_id = process_id

    def name(self) -> str:
        return "psql"

    def exe(self) -> str:
        return "/usr/bin/psql"

    def username(self) -> str:
        return "dev-user"


class FakeMonotonicClock:
    def __init__(self) -> None:
        self._value = 0.0

    def __call__(self) -> float:
        return self._value

    def advance(self, seconds: float) -> None:
        self._value += seconds


class FakeStopSignal:
    def __init__(self, clock: FakeMonotonicClock, *, stop_after_waits: int) -> None:
        self._clock = clock
        self._stop_after_waits = stop_after_waits
        self._is_set = False
        self.waits: list[float] = []

    def wait(self, timeout: float | None = None) -> bool:
        wait_seconds = float(timeout or 0.0)
        self.waits.append(wait_seconds)
        if len(self.waits) >= self._stop_after_waits:
            self._is_set = True
            return True

        self._clock.advance(wait_seconds)
        return False

    def set(self) -> None:
        self._is_set = True

    def is_set(self) -> bool:
        return self._is_set


class SignalFreeAgentRunner(AgentRunner):
    def _install_signal_handlers(self, _identity: DeviceIdentity) -> None:
        return None
