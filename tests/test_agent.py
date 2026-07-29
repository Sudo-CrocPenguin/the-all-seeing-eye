import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from agent.app import cli as agent_cli
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
from agent.app.state import AgentState, AgentStateError, JsonAgentStateStore, LinkedCompanyState
from agent.app.transport import AgentTransportError, AuditApiClient, InsecureBackendUrlError
from agent.app.windows_service import (
    WINDOWS_SERVICE_DESCRIPTION,
    WINDOWS_SERVICE_DISPLAY_NAME,
    WINDOWS_SERVICE_NAME,
    load_pywin32_modules,
)


def test_agent_settings_from_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://backend.local:8000/")
    monkeypatch.setenv("AGENT_DEVICE_ID", "device-123")
    monkeypatch.setenv("AGENT_COMPANY_ID", "company-1")
    monkeypatch.setenv("AGENT_COMPANY_DEVICE_LINK_ID", "link-1")
    monkeypatch.setenv("AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AGENT_TOKEN_HEADER", "X-Custom-Agent-Token")
    monkeypatch.setenv("AGENT_HEARTBEAT_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("AGENT_SCAN_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("AGENT_REQUEST_RETRY_BACKOFF_SECONDS", "7")
    monkeypatch.setenv("AGENT_STATE_FILE", "/tmp/the-all-seeing-eye-agent-state.json")
    monkeypatch.setenv("AGENT_QUEUE_FILE", "/tmp/the-all-seeing-eye-agent-queue.jsonl")
    monkeypatch.setenv("AGENT_SERVICE_MAP_FILE", "/tmp/the-all-seeing-eye-service-map.json")
    monkeypatch.setenv("AGENT_REVERSE_DNS_ENABLED", "false")
    monkeypatch.setenv("AGENT_ALLOW_INSECURE_TRANSPORT", "true")

    settings = AgentSettings.from_environment()

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-123"
    assert settings.company_id == "company-1"
    assert settings.company_device_link_id == "link-1"
    assert settings.agent_token == "agent-token"
    assert settings.agent_token_header == "X-Custom-Agent-Token"
    assert settings.heartbeat_interval_seconds == 30
    assert settings.scan_interval_seconds == 5
    assert settings.request_retry_backoff_seconds == 7
    assert str(settings.state_file) == "/tmp/the-all-seeing-eye-agent-state.json"
    assert str(settings.queue_file) == "/tmp/the-all-seeing-eye-agent-queue.jsonl"
    assert str(settings.service_map_file) == "/tmp/the-all-seeing-eye-service-map.json"
    assert not settings.reverse_dns_enabled
    assert settings.allow_insecure_transport


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
                "AGENT_COMPANY_ID=company-file",
                "AGENT_COMPANY_DEVICE_LINK_ID=link-file",
                "AGENT_TOKEN=token-file",
                "AGENT_HEARTBEAT_INTERVAL_SECONDS=20",
            ],
        ),
        encoding="utf-8",
    )

    settings = AgentSettings.from_environment(env_file)

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-file"
    assert settings.company_id == "company-file"
    assert settings.company_device_link_id == "link-file"
    assert settings.agent_token == "token-file"
    assert settings.heartbeat_interval_seconds == 20


def test_cli_preserves_service_map_file_from_environment(
    tmp_path: Any,
    monkeypatch: Any,
) -> None:
    service_map_file = tmp_path / "service-map.json"
    captured: dict[str, object] = {}

    class FakeCliRunner:
        def __init__(self, settings: AgentSettings) -> None:
            captured["settings"] = settings

        def run_once(self) -> None:
            captured["run_once"] = True

        def run_forever(self) -> None:
            captured["run_forever"] = True

    monkeypatch.setenv("AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AGENT_SERVICE_MAP_FILE", str(service_map_file))
    monkeypatch.setattr(agent_cli, "AgentRunner", FakeCliRunner)
    monkeypatch.setattr(sys, "argv", ["agent", "--once"])

    agent_cli.main()

    settings = captured["settings"]
    assert isinstance(settings, AgentSettings)
    assert settings.service_map_file == service_map_file
    assert captured["run_once"] is True


def test_environment_variables_override_env_file(tmp_path: Any, monkeypatch: Any) -> None:
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://env.local:8000")
    env_file = tmp_path / "agent.env"
    env_file.write_text("AGENT_BACKEND_URL=http://file.local:8000\n", encoding="utf-8")

    settings = AgentSettings.from_environment(env_file)

    assert settings.backend_url == "http://env.local:8000"


def test_agent_state_store_loads_empty_state_when_file_is_missing(tmp_path: Any) -> None:
    state = JsonAgentStateStore(tmp_path / "agent-state.json").load()

    assert state == AgentState()


def test_agent_state_store_persists_active_company(tmp_path: Any) -> None:
    state_file = tmp_path / "state" / "agent-state.json"
    store = JsonAgentStateStore(state_file)
    state = AgentState(device_id="device-1", recording_enabled=True).upsert_link(
        LinkedCompanyState(
            company_id="company-1",
            company_device_link_id="link-1",
            company_name="Acme",
            linked_at="2026-07-29T10:00:00Z",
        ),
    )

    saved_state = store.save(state.select_company("company-1"))

    loaded_state = store.load()
    assert loaded_state == saved_state
    assert loaded_state.active_company is not None
    assert loaded_state.active_company.company_name == "Acme"


def test_agent_state_rejects_unknown_active_company() -> None:
    state = AgentState().upsert_link(
        LinkedCompanyState(
            company_id="company-1",
            company_device_link_id="link-1",
            company_name="Acme",
            status="REVOKED",
            revoked_at="2026-07-29T10:00:00Z",
        ),
    )

    try:
        state.select_company("company-1")
    except AgentStateError as exc:
        assert "no esta vinculada" in str(exc)
    else:
        raise AssertionError("No debe seleccionar una empresa revocada")


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
    payload = connections[0].to_backend_payload(
        identity,
        company_id="company-1",
        company_device_link_id="link-1",
    )
    assert payload["device_id"] == "device-1"
    assert payload["company_id"] == "company-1"
    assert payload["company_device_link_id"] == "link-1"
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


def test_network_collector_can_skip_reverse_dns(monkeypatch: Any) -> None:
    raw_connection = SimpleNamespace(
        type=1,
        laddr=SimpleNamespace(ip="192.168.1.10", port=51515),
        raddr=SimpleNamespace(ip="93.184.216.34", port=443),
        status="ESTABLISHED",
        pid=None,
    )
    monkeypatch.setattr(
        "agent.app.network_collector.psutil.net_connections",
        lambda kind: [raw_connection],
    )
    monkeypatch.setattr("agent.app.network_collector.psutil.users", lambda: [])

    def fail_reverse_dns(_destination_ip: str) -> tuple[str, list[str], list[str]]:
        raise AssertionError("reverse DNS no debe ejecutarse cuando esta desactivado")

    monkeypatch.setattr("agent.app.network_collector.gethostbyaddr", fail_reverse_dns)
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(),
    )

    connections = NetworkConnectionCollector(reverse_dns_enabled=False).collect(identity)

    assert len(connections) == 1
    assert connections[0].destination_host is None


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
        AgentSettings(
            heartbeat_interval_seconds=1,
            scan_interval_seconds=1,
            company_id="company-1",
            company_device_link_id="link-1",
        ),
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
    assert api_client.network_events[0]["company_id"] == "company-1"
    assert api_client.network_events[0]["company_device_link_id"] == "link-1"


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
            company_id="company-1",
            company_device_link_id="link-1",
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


def test_runner_forever_refreshes_identity_when_network_metadata_changes() -> None:
    first_identity = DeviceIdentity(
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
    updated_identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(
            NetworkInterface(
                name="tun0",
                local_ip="10.8.0.10",
                mac_address=None,
                is_up=True,
            ),
        ),
    )
    api_client = FakeAuditApiClient()
    network_collector = IdentityAwareNetworkCollector()
    clock = FakeMonotonicClock()
    stop_signal = FakeStopSignal(clock, stop_after_waits=2)
    runner = SignalFreeAgentRunner(
        AgentSettings(
            heartbeat_interval_seconds=10,
            scan_interval_seconds=3,
            network_event_dedup_seconds=0,
            company_id="company-1",
            company_device_link_id="link-1",
        ),
        identity_collector=CyclingIdentityCollector([first_identity, updated_identity]),
        network_collector=network_collector,
        api_client=api_client,
        stop_signal=stop_signal,
        monotonic_clock=clock,
    )

    runner.run_forever()

    assert api_client.registered_devices == ["device-1", "device-1"]
    assert api_client.lifecycle_events == [
        "AGENT_STARTED",
        "AGENT_CONFIG_CHANGED",
        "AGENT_STOPPING",
        "AGENT_STOPPED",
    ]
    assert network_collector.seen_identities == [updated_identity]
    assert api_client.network_events[0]["local_ip"] == "10.8.0.10"
    assert api_client.network_events[0]["network_interface"] == "tun0"
    assert api_client.network_events[0]["company_id"] == "company-1"


def test_runner_requires_agent_token_when_using_real_client() -> None:
    try:
        AgentRunner(AgentSettings())
    except AgentConfigurationError as exc:
        assert "AGENT_TOKEN" in str(exc)
    else:
        raise AssertionError("AgentRunner debe exigir AGENT_TOKEN")


def test_runner_requires_company_context_before_audit_events() -> None:
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(),
    )
    api_client = FakeAuditApiClient()
    runner = AgentRunner(
        AgentSettings(),
        identity_collector=FakeIdentityCollector(identity),
        network_collector=FakeNetworkCollector([]),
        api_client=api_client,
    )

    try:
        runner.run_once()
    except AgentConfigurationError as exc:
        assert "AGENT_COMPANY_ID" in str(exc)
        assert "AGENT_COMPANY_DEVICE_LINK_ID" in str(exc)
    else:
        raise AssertionError("AgentRunner debe exigir empresa activa para auditoria")

    assert api_client.lifecycle_events == []
    assert api_client.network_events == []


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
        "https://backend.local:8000",
        agent_token="agent-token",
        agent_token_header="X-Agent-Token",
    )

    client.register_device(identity)

    assert captured_headers["X-agent-token"] == "agent-token"


def test_api_client_rejects_non_local_http_backend_by_default() -> None:
    try:
        AuditApiClient("http://backend.local:8000", agent_token="agent-token")
    except InsecureBackendUrlError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("El agente debe rechazar HTTP no-local por defecto")


def test_api_client_allows_loopback_http_backend_by_default() -> None:
    client = AuditApiClient("http://127.0.0.1:8000", agent_token="agent-token")

    assert isinstance(client, AuditApiClient)


def test_api_client_allows_explicit_insecure_transport_override() -> None:
    client = AuditApiClient(
        "http://backend.local:8000",
        agent_token="agent-token",
        allow_insecure_transport=True,
    )

    assert isinstance(client, AuditApiClient)


def test_runner_reports_insecure_backend_as_configuration_error() -> None:
    try:
        AgentRunner(
            AgentSettings(
                backend_url="http://backend.local:8000",
                agent_token="agent-token",
            ),
        )
    except AgentConfigurationError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("AgentRunner debe reportar transporte inseguro como configuracion")


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
            "company_id": "company-1",
            "company_device_link_id": "link-1",
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


def test_queued_client_raises_and_does_not_queue_fatal_errors(tmp_path: Any) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    client = QueuedAuditApiClient(
        FatalPostJsonClient(),
        LocalAgentRequestQueue(queue_file),
        retry_backoff_seconds=30,
    )

    try:
        client.send_network_event(
            {
                "device_id": "device-1",
                "company_id": "company-1",
                "company_device_link_id": "link-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "Linux",
                "agent_version": "0.1.0",
                "occurred_at": "2026-07-27T14:00:00+00:00",
                "protocol": "TCP",
            },
        )
    except AgentTransportError as exc:
        assert not exc.retryable
    else:
        raise AssertionError("La cola no debe ocultar errores fatales")

    assert LocalAgentRequestQueue(queue_file).read_all() == []


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
            "company_id": "company-1",
            "company_device_link_id": "link-1",
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


def test_queued_client_discards_legacy_audit_events_without_company_context(
    tmp_path: Any,
) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    queue = LocalAgentRequestQueue(queue_file)
    queue.enqueue(
        QueuedRequest(
            path="/api/v1/audit/lifecycle-events",
            payload={
                "event_type": "AGENT_STARTED",
                "device_id": "device-1",
            },
        ),
    )
    queue.enqueue(
        QueuedRequest(
            path="/api/v1/audit/network-events",
            payload={
                "device_id": "device-1",
                "company_id": "company-1",
                "company_device_link_id": "link-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "Linux",
                "agent_version": "0.1.0",
                "occurred_at": "2026-07-27T14:00:01+00:00",
                "protocol": "TCP",
            },
        ),
    )
    post_client = RejectingLegacyAuditPostJsonClient()
    client = QueuedAuditApiClient(post_client, queue, retry_backoff_seconds=30)

    assert client.flush()

    assert [request[0] for request in post_client.requests] == [
        "/api/v1/audit/lifecycle-events",
        "/api/v1/audit/network-events",
    ]
    assert queue.read_all() == []


def test_queued_client_queues_current_request_when_pending_flush_is_blocked(
    tmp_path: Any,
) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    queue = LocalAgentRequestQueue(queue_file)
    queue.enqueue(
        QueuedRequest(
            path="/api/v1/devices",
            payload={"device_id": "device-1"},
        ),
    )
    post_client = RecordingFailingPostJsonClient()
    clock = FakeMonotonicClock()
    client = QueuedAuditApiClient(
        post_client,
        queue,
        retry_backoff_seconds=30,
        monotonic_clock=clock,
    )
    identity = DeviceIdentity(
        device_id="device-1",
        hostname="DEV-LAPTOP-001",
        os_name="Linux",
        agent_version="0.1.0",
        interfaces=(),
    )

    lifecycle_response = client.send_lifecycle_event(
        identity,
        "AGENT_STARTED",
        "2026-07-27T14:00:00+00:00",
        company_id="company-1",
        company_device_link_id="link-1",
    )
    network_response = client.send_network_event(
        {
            "device_id": "device-1",
            "company_id": "company-1",
            "company_device_link_id": "link-1",
            "hostname": "DEV-LAPTOP-001",
            "os_name": "Linux",
            "agent_version": "0.1.0",
            "occurred_at": "2026-07-27T14:00:01+00:00",
            "protocol": "TCP",
        },
    )

    assert lifecycle_response == {}
    assert network_response == {}
    assert [request[0] for request in post_client.requests] == ["/api/v1/devices"]
    assert [request.path for request in queue.read_all()] == [
        "/api/v1/devices",
        "/api/v1/audit/lifecycle-events",
        "/api/v1/audit/network-events",
    ]


def test_local_queue_ignores_corrupt_jsonl_records(tmp_path: Any) -> None:
    queue_file = tmp_path / "agent-queue.jsonl"
    valid_request = QueuedRequest(
        path="/api/v1/devices",
        payload={"device_id": "device-1"},
    )
    queue_file.write_text(
        "\n".join(
            [
                '{"payload": {"device_id": "device-1"}, "path": "/api/v1/devices"}',
                "{json cortado",
                '{"payload": [], "path": "/api/v1/audit/network-events"}',
            ],
        ),
        encoding="utf-8",
    )

    requests = LocalAgentRequestQueue(queue_file).read_all()

    assert requests == [valid_request]
    assert LocalAgentRequestQueue(queue_file).read_all() == [valid_request]


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


def test_service_map_invalid_json_degrades_to_empty_map(tmp_path: Any) -> None:
    service_map_file = tmp_path / "service-map.json"
    service_map_file.write_text("{json invalido", encoding="utf-8")

    service_map = ServiceMap.from_file(service_map_file)

    assert service_map.find("10.0.0.25", 5432) is None


def test_service_map_invalid_entry_degrades_to_empty_map(tmp_path: Any) -> None:
    service_map_file = tmp_path / "service-map.json"
    service_map_file.write_text(
        '[{"destination_ip": "10.0.0.25", "destination_port": "5432"}]',
        encoding="utf-8",
    )

    service_map = ServiceMap.from_file(service_map_file)

    assert service_map.find("10.0.0.25", 5432) is None


class FakeIdentityCollector:
    def __init__(self, identity: DeviceIdentity) -> None:
        self._identity = identity

    def collect(self) -> DeviceIdentity:
        return self._identity


class CyclingIdentityCollector:
    def __init__(self, identities: list[DeviceIdentity]) -> None:
        self._identities = identities
        self._index = 0

    def collect(self) -> DeviceIdentity:
        if self._index >= len(self._identities):
            return self._identities[-1]
        identity = self._identities[self._index]
        self._index += 1
        return identity


class FakeNetworkCollector:
    def __init__(self, connections: list[ObservedNetworkConnection]) -> None:
        self._connections = connections

    def collect(self, _identity: DeviceIdentity) -> list[ObservedNetworkConnection]:
        return self._connections


class IdentityAwareNetworkCollector:
    def __init__(self) -> None:
        self.seen_identities: list[DeviceIdentity] = []

    def collect(self, identity: DeviceIdentity) -> list[ObservedNetworkConnection]:
        self.seen_identities.append(identity)
        interface = identity.interfaces[0]
        return [
            ObservedNetworkConnection(
                occurred_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
                protocol="TCP",
                local_ip=interface.local_ip,
                local_port=51515,
                destination_ip="93.184.216.34",
                destination_port=443,
                status="ESTABLISHED",
                network_interface=interface.name,
                mac_address=interface.mac_address,
            ),
        ]


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
        company_id: str,
        company_device_link_id: str,
        reason: str | None = None,
    ) -> dict[str, object]:
        self.lifecycle_events.append(event_type)
        return {
            "company_id": company_id,
            "company_device_link_id": company_device_link_id,
            "reason": reason or "",
        }

    def send_network_event(self, payload: dict[str, object]) -> dict[str, object]:
        self.network_events.append(payload)
        return {}


class FailingPostJsonClient:
    def post_json(self, _path: str, _payload: dict[str, object]) -> dict[str, object]:
        raise AgentTransportError("backend no disponible")


class FatalPostJsonClient:
    def post_json(self, _path: str, _payload: dict[str, object]) -> dict[str, object]:
        raise AgentTransportError("token invalido", retryable=False)


class RecordingPostJsonClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append((path, payload))
        return {"status": "ok"}


class RejectingLegacyAuditPostJsonClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append((path, payload))
        if path.startswith("/api/v1/audit/") and (
            not payload.get("company_id") or not payload.get("company_device_link_id")
        ):
            raise AgentTransportError("payload legacy", retryable=False, status_code=422)
        return {"status": "ok"}


class RecordingFailingPostJsonClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, object]]] = []

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        self.requests.append((path, payload))
        raise AgentTransportError("backend no disponible")


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
