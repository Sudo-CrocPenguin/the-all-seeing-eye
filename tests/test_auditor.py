import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auditor.app import cli as auditor_cli
from auditor.app.config import AuditorSettings
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


class FakeAuditorCliApiClient:
    def __init__(self) -> None:
        self.created_company: tuple[str, str] | None = None
        self.verified_access: tuple[str, str, str, str] | None = None

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
