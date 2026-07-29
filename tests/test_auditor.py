import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auditor.app import cli as auditor_cli
from auditor.app.config import AuditorSettings
from auditor.app.export import build_audit_export
from auditor.app.state import AuditorSessionState, JsonAuditorSessionStore


def test_auditor_settings_from_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("AUDITOR_BACKEND_URL", "http://backend.local:8000/")
    monkeypatch.setenv("AUDITOR_DEVICE_ID", "device-auditor")
    monkeypatch.setenv("AUDITOR_AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AUDITOR_AGENT_TOKEN_HEADER", "X-Custom-Agent")
    monkeypatch.setenv("AUDITOR_SESSION_HEADER", "X-Custom-Session")
    monkeypatch.setenv("AUDITOR_REQUEST_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("AUDITOR_SESSION_FILE", "/tmp/the-all-seeing-eye-auditor.json")
    monkeypatch.setenv("AUDITOR_ALLOW_INSECURE_TRANSPORT", "true")

    settings = AuditorSettings.from_environment()

    assert settings.backend_url == "http://backend.local:8000"
    assert settings.device_id == "device-auditor"
    assert settings.agent_token == "agent-token"
    assert settings.agent_token_header == "X-Custom-Agent"
    assert settings.auditor_session_header == "X-Custom-Session"
    assert settings.request_timeout_seconds == 7
    assert settings.session_file == Path("/tmp/the-all-seeing-eye-auditor.json")
    assert settings.allow_insecure_transport


def test_auditor_settings_use_agent_fallbacks(monkeypatch: Any) -> None:
    monkeypatch.delenv("AUDITOR_BACKEND_URL", raising=False)
    monkeypatch.delenv("AUDITOR_DEVICE_ID", raising=False)
    monkeypatch.delenv("AUDITOR_AGENT_TOKEN", raising=False)
    monkeypatch.setenv("AGENT_BACKEND_URL", "http://agent-backend.local:8000/")
    monkeypatch.setenv("AGENT_DEVICE_ID", "device-agent")
    monkeypatch.setenv("AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AGENT_TOKEN_HEADER", "X-Agent-Custom")
    monkeypatch.setenv("AGENT_ALLOW_INSECURE_TRANSPORT", "true")

    settings = AuditorSettings.from_environment()

    assert settings.backend_url == "http://agent-backend.local:8000"
    assert settings.device_id == "device-agent"
    assert settings.agent_token == "agent-token"
    assert settings.agent_token_header == "X-Agent-Custom"
    assert settings.allow_insecure_transport


def test_auditor_session_store_roundtrip(tmp_path: Any) -> None:
    session_file = tmp_path / "auditor-session.json"
    store = JsonAuditorSessionStore(session_file)
    session = AuditorSessionState(
        auditor_session_id="session-1",
        company_id="company-1",
        device_id="device-1",
        created_at="2026-07-29T10:00:00+00:00",
        expires_at="2026-07-29T22:00:00+00:00",
        scopes=("company:read", "audit:read"),
    )

    saved_session = store.save(session)
    loaded_session = store.load()

    assert saved_session == session
    assert loaded_session == session
    assert not session.is_expired(datetime(2026, 7, 29, 21, 0, tzinfo=UTC))
    assert session.is_expired(datetime(2026, 7, 29, 22, 1, tzinfo=UTC))


def test_cli_company_create_calls_backend(
    monkeypatch: Any,
    capsys: Any,
) -> None:
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ase-auditor", "company", "create", "--name", "Acme", "--phone", "+15550000000"],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.created_company == ("Acme", "+15550000000")
    assert "Empresa creada: Acme (company-1)" in output


def test_cli_access_verify_stores_session(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setenv("AUDITOR_AGENT_TOKEN", "agent-token")
    monkeypatch.setenv("AUDITOR_DEVICE_ID", "device-1")
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "access",
            "verify",
            "--company",
            "company-1",
            "--request",
            "access-1",
            "--code",
            "123456",
        ],
    )

    auditor_cli.main()

    stored_session = JsonAuditorSessionStore(session_file).load()
    output = capsys.readouterr().out
    assert fake_client.verified_access == ("company-1", "access-1", "device-1", "123456")
    assert stored_session is not None
    assert stored_session.auditor_session_id == "session-1"
    assert stored_session.company_id == "company-1"
    assert "Sesion auditor guardada: session-1" in output


def test_cli_enrollment_code_create_uses_local_session(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "enrollment-code",
            "create",
            "--ttl-seconds",
            "3600",
            "--max-uses",
            "3",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.created_enrollment_code == ("company-1", "session-1", 3600, 3)
    assert "Codigo de vinculacion: ENROLL-123" in output


def test_cli_enrollment_requests_approve_uses_local_session(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "enrollment-requests",
            "approve",
            "--request",
            "enrollment-1",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.reviewed_enrollment_request == (
        "company-1",
        "enrollment-1",
        "session-1",
        "ACCEPT",
    )
    assert "Solicitud revisada: enrollment-1 status=ACCEPTED link=link-1" in output


def test_cli_summary_uses_local_session(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ase-auditor", "--session-file", str(session_file), "summary"],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.requested_summary == ("company-1", "session-1")
    assert "Company: Acme (company-1)" in output
    assert "Connected devices: 2" in output


def test_cli_history_network_uses_session_filters(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "history",
            "network",
            "--from",
            "2026-07-29T10:00:00+00:00",
            "--to",
            "2026-07-29T11:00:00+00:00",
            "--device-id",
            "device-1",
            "--protocol",
            "TCP",
            "--limit",
            "50",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.network_history_request == (
        "session-1",
        {
            "device_id": "device-1",
            "local_ip": None,
            "public_ip": None,
            "destination_host": None,
            "destination_ip": None,
            "protocol": "TCP",
            "from": "2026-07-29T10:00:00+00:00",
            "to": "2026-07-29T11:00:00+00:00",
            "limit": 50,
        },
    )
    assert "device=device-1 protocol=TCP destination=api.example.com:443" in output


def test_cli_history_lifecycle_uses_session_filters(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "history",
            "lifecycle",
            "--event-type",
            "AGENT_STOPPED",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.lifecycle_history_request is not None
    assert fake_client.lifecycle_history_request[0] == "session-1"
    assert fake_client.lifecycle_history_request[1]["event_type"] == "AGENT_STOPPED"
    assert "device=device-1 type=AGENT_STOPPED reason=recording disabled" in output


def test_cli_history_movements_requires_device_context(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "history",
            "movements",
            "--device-id",
            "device-1",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.movements_history_request == (
        "session-1",
        "device-1",
        {"from": None, "to": None, "limit": 100},
    )
    assert "device=device-1 local_ip=192.168.1.10" in output


def test_cli_history_incident_window_prints_counts(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "history",
            "incident-window",
            "--from",
            "2026-07-29T10:00:00+00:00",
            "--to",
            "2026-07-29T10:30:00+00:00",
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    assert fake_client.incident_window_request == (
        "session-1",
        {
            "from": "2026-07-29T10:00:00+00:00",
            "to": "2026-07-29T10:30:00+00:00",
            "at": None,
            "window_seconds": 900,
            "limit": 500,
        },
    )
    assert "Active devices: 1" in output
    assert "Network events: 1" in output


def test_build_audit_export_includes_metadata_and_company_filtered_events() -> None:
    fake_client = FakeAuditorCliApiClient()
    session = AuditorSessionState(
        auditor_session_id="session-1",
        company_id="company-1",
        device_id="device-1",
        expires_at="2999-01-01T00:00:00+00:00",
        scopes=("audit:read",),
    )

    export_payload = build_audit_export(
        fake_client,
        session,
        from_datetime="2026-07-29T10:00:00+00:00",
        to_datetime="2026-07-29T11:00:00+00:00",
        device_id="device-1",
        limit=500,
        exported_at=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
    )

    assert export_payload["format_version"] == "audit-export/v1"
    assert export_payload["metadata"]["company"]["company_id"] == "company-1"
    assert export_payload["metadata"]["filters"]["device_id"] == "device-1"
    assert export_payload["events"]["network_events"][0]["company_id"] == "company-1"
    assert export_payload["events"]["lifecycle_events"][0]["company_id"] == "company-1"
    assert export_payload["events"]["device_movements"][0]["company_id"] == "company-1"


def test_cli_export_json_writes_file(
    tmp_path: Any,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    session_file = tmp_path / "auditor-session.json"
    export_file = tmp_path / "exports" / "audit.json"
    _save_valid_session(session_file)
    fake_client = FakeAuditorCliApiClient()
    monkeypatch.setattr(auditor_cli, "_build_auditor_api_client", lambda _settings: fake_client)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ase-auditor",
            "--session-file",
            str(session_file),
            "export-json",
            "--from",
            "2026-07-29T10:00:00+00:00",
            "--to",
            "2026-07-29T11:00:00+00:00",
            "--device-id",
            "device-1",
            "--output",
            str(export_file),
        ],
    )

    auditor_cli.main()

    output = capsys.readouterr().out
    exported_payload = json.loads(export_file.read_text(encoding="utf-8"))
    assert "Export JSON:" in output
    assert exported_payload["metadata"]["company"]["company_id"] == "company-1"
    assert exported_payload["metadata"]["filters"]["from"] == "2026-07-29T10:00:00+00:00"
    assert exported_payload["events"]["network_events"][0]["company_id"] == "company-1"
    assert fake_client.movements_history_request == (
        "session-1",
        "device-1",
        {
            "from": "2026-07-29T10:00:00+00:00",
            "to": "2026-07-29T11:00:00+00:00",
            "limit": 500,
        },
    )


def _save_valid_session(session_file: Path) -> None:
    JsonAuditorSessionStore(session_file).save(
        AuditorSessionState(
            auditor_session_id="session-1",
            company_id="company-1",
            device_id="device-1",
            created_at="2026-07-29T10:00:00+00:00",
            expires_at="2999-01-01T00:00:00+00:00",
            scopes=("company:read", "devices:read", "devices:approve", "audit:read"),
        ),
    )


class FakeAuditorCliApiClient:
    def __init__(self) -> None:
        self.created_company: tuple[str, str] | None = None
        self.verified_access: tuple[str, str, str, str] | None = None
        self.created_enrollment_code: tuple[str, str, int, int] | None = None
        self.reviewed_enrollment_request: tuple[str, str, str, str] | None = None
        self.requested_summary: tuple[str, str] | None = None
        self.network_history_request: tuple[str, dict[str, object | None]] | None = None
        self.lifecycle_history_request: tuple[str, dict[str, object | None]] | None = None
        self.movements_history_request: (
            tuple[str, str, dict[str, object | None]] | None
        ) = None
        self.incident_window_request: tuple[str, dict[str, object | None]] | None = None

    def create_company(self, *, name: str, phone_number: str) -> dict[str, Any]:
        self.created_company = (name, phone_number)
        return {
            "company_id": "company-1",
            "name": name,
            "phone_number": phone_number,
            "status": "ACTIVE",
            "created_at": "2026-07-29T10:00:00+00:00",
        }

    def request_auditor_access(self, *, company_id: str, device_id: str) -> dict[str, Any]:
        return {
            "auditor_access_request_id": "access-1",
            "company_id": company_id,
            "device_id": device_id,
            "requested_at": "2026-07-29T10:00:00+00:00",
            "expires_at": "2026-07-29T10:10:00+00:00",
            "status": "PENDING",
            "delivery_channel": "local_response",
            "verification_code": "123456",
        }

    def verify_auditor_access(
        self,
        *,
        company_id: str,
        auditor_access_request_id: str,
        device_id: str,
        verification_code: str,
    ) -> dict[str, Any]:
        self.verified_access = (
            company_id,
            auditor_access_request_id,
            device_id,
            verification_code,
        )
        return {
            "auditor_session_id": "session-1",
            "company_id": company_id,
            "device_id": device_id,
            "created_at": "2026-07-29T10:00:00+00:00",
            "expires_at": "2026-07-29T22:00:00+00:00",
            "scopes": ["company:read", "devices:read", "devices:approve", "audit:read"],
            "revoked_at": None,
        }

    def create_enrollment_code(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        ttl_seconds: int,
        max_uses: int,
    ) -> dict[str, Any]:
        self.created_enrollment_code = (
            company_id,
            auditor_session_id,
            ttl_seconds,
            max_uses,
        )
        return {
            "enrollment_code_id": "code-1",
            "company_id": company_id,
            "code": "ENROLL-123",
            "created_at": "2026-07-29T10:00:00+00:00",
            "expires_at": "2026-07-29T11:00:00+00:00",
            "max_uses": max_uses,
            "used_count": 0,
        }

    def list_enrollment_requests(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "enrollment_request_id": "enrollment-1",
                "company_id": company_id,
                "device_id": "device-1",
                "requested_at": "2026-07-29T10:00:00+00:00",
                "status": status_filter or "PENDING",
                "reviewed_by_auditor_session_id": None,
                "reviewed_at": None,
                "device_fingerprint_snapshot": {},
            },
        ]

    def review_enrollment_request(
        self,
        *,
        company_id: str,
        enrollment_request_id: str,
        auditor_session_id: str,
        decision: str,
    ) -> dict[str, Any]:
        self.reviewed_enrollment_request = (
            company_id,
            enrollment_request_id,
            auditor_session_id,
            decision,
        )
        return {
            "enrollment_request_id": enrollment_request_id,
            "company_id": company_id,
            "device_id": "device-1",
            "status": "ACCEPTED" if decision == "ACCEPT" else "DENIED",
            "link": {
                "company_device_link_id": "link-1",
                "company_id": company_id,
                "device_id": "device-1",
                "linked_at": "2026-07-29T10:01:00+00:00",
                "status": "ACTIVE",
                "revoked_at": None,
                "revoked_by_device": False,
                "revoked_by_auditor_session_id": None,
            },
        }

    def get_company_summary(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
    ) -> dict[str, Any]:
        self.requested_summary = (company_id, auditor_session_id)
        return {
            "company_id": company_id,
            "name": "Acme",
            "status": "ACTIVE",
            "linked_devices": 3,
            "active_links": 3,
            "connected_devices": 2,
            "without_report_devices": 1,
            "pending_enrollment_requests": 4,
            "active_auditor_sessions": 1,
        }

    def search_network_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        self.network_history_request = (auditor_session_id, filters)
        return [
            {
                "event_id": "network-1",
                "occurred_at": "2026-07-29T10:15:00+00:00",
                "device_id": "device-1",
                "company_id": "company-1",
                "company_device_link_id": "link-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "Linux",
                "agent_version": "0.1.0",
                "protocol": "TCP",
                "local_ip": "192.168.1.10",
                "public_ip": "198.51.100.10",
                "destination_host": "api.example.com",
                "destination_ip": "203.0.113.10",
                "destination_port": 443,
                "http_method": None,
                "http_status_code": None,
                "bytes_sent": 10,
                "bytes_received": 20,
                "network_interface": "eth0",
                "mac_address": "00:11:22:33:44:55",
                "local_username": "alice",
                "process_id": 123,
                "process_name": "curl",
                "process_executable": "/usr/bin/curl",
                "service_name": None,
                "request_metadata": {},
                "response_metadata": {},
                "created_at": "2026-07-29T10:15:01+00:00",
            },
        ]

    def search_lifecycle_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        self.lifecycle_history_request = (auditor_session_id, filters)
        return [
            {
                "event_id": "lifecycle-1",
                "event_type": "AGENT_STOPPED",
                "occurred_at": "2026-07-29T10:20:00+00:00",
                "device_id": "device-1",
                "company_id": "company-1",
                "company_device_link_id": "link-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
                "public_ip": "198.51.100.10",
                "reason": "recording disabled",
                "last_seen_at": None,
                "detected_at": None,
                "downtime_seconds": None,
                "created_at": "2026-07-29T10:20:01+00:00",
            },
        ]

    def search_device_movements(
        self,
        *,
        auditor_session_id: str,
        device_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        self.movements_history_request = (auditor_session_id, device_id, filters)
        return [
            {
                "event_id": "movement-1",
                "occurred_at": "2026-07-29T10:15:00+00:00",
                "created_at": "2026-07-29T10:15:01+00:00",
                "movement_type": "NETWORK_CONNECTION",
                "device_id": device_id,
                "company_id": "company-1",
                "company_device_link_id": "link-1",
                "hostname": "DEV-LAPTOP-001",
                "local_ip": "192.168.1.10",
                "public_ip": "198.51.100.10",
                "summary": "api.example.com:443",
            },
        ]

    def query_incident_window(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> dict[str, Any]:
        self.incident_window_request = (auditor_session_id, filters)
        return {
            "from_datetime": "2026-07-29T10:00:00+00:00",
            "to_datetime": "2026-07-29T10:30:00+00:00",
            "active_devices": [{"device_id": "device-1"}],
            "devices_without_report": [],
            "devices_seen_after_window": [],
            "network_events": [{"event_id": "network-1"}],
            "lifecycle_events": [],
        }
