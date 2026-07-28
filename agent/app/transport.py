import json
from dataclasses import asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent.app.device_identity import DeviceIdentity


class AgentTransportError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def build_device_registration_payload(identity: DeviceIdentity) -> dict[str, Any]:
    return {
        "device_id": identity.device_id,
        "hostname": identity.hostname,
        "os_name": identity.os_name,
        "agent_version": identity.agent_version,
        "metadata": {
            "interfaces": json.dumps(
                [asdict(interface) for interface in identity.interfaces],
            ),
        },
    }


def build_lifecycle_event_payload(
    identity: DeviceIdentity,
    event_type: str,
    occurred_at: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "device_id": identity.device_id,
        "hostname": identity.hostname,
        "agent_version": identity.agent_version,
        "local_ip": identity.primary_local_ip,
        "reason": reason,
    }


class AuditApiClient:
    def __init__(
        self,
        backend_url: str,
        *,
        agent_token: str,
        agent_token_header: str = "X-Agent-Token",
        timeout_seconds: int = 10,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._agent_token = agent_token
        self._agent_token_header = agent_token_header
        self._timeout_seconds = timeout_seconds

    def register_device(self, identity: DeviceIdentity) -> dict[str, Any]:
        return self.post_json("/api/v1/devices", build_device_registration_payload(identity))

    def send_lifecycle_event(
        self,
        identity: DeviceIdentity,
        event_type: str,
        occurred_at: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/api/v1/audit/lifecycle-events",
            build_lifecycle_event_payload(
                identity,
                event_type,
                occurred_at,
                reason=reason,
            ),
        )

    def send_network_event(self, payload: dict[str, object]) -> dict[str, Any]:
        return self.post_json("/api/v1/audit/network-events", payload)

    def post_json(self, path: str, payload: dict[str, Any] | dict[str, object]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        request = Request(
            url=f"{self._backend_url}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "the-all-seeing-eye-agent/0.1.0",
                self._agent_token_header: self._agent_token,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw_response = response.read()
        except HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            raise AgentTransportError(
                f"Backend respondio {exc.code} al enviar {path}: {error_body}",
                retryable=_is_retryable_http_status(exc.code),
            ) from exc
        except URLError as exc:
            raise AgentTransportError(f"No se pudo conectar con el backend: {exc.reason}") from exc

        if not raw_response:
            return {}

        decoded = json.loads(raw_response.decode())
        if not isinstance(decoded, dict):
            raise AgentTransportError(f"Respuesta inesperada del backend para {path}")
        return decoded


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code == 408 or status_code == 429 or status_code >= 500
