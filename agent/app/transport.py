import json
from dataclasses import asdict
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from agent.app.config import AGENT_VERSION
from agent.app.device_identity import DeviceIdentity


class InsecureBackendUrlError(ValueError):
    pass


class AgentTransportError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


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
    company_id: str,
    company_device_link_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "occurred_at": occurred_at,
        "device_id": identity.device_id,
        "company_id": company_id,
        "company_device_link_id": company_device_link_id,
        "hostname": identity.hostname,
        "agent_version": identity.agent_version,
        "local_ip": identity.primary_local_ip,
        "reason": reason,
    }


def build_device_enrollment_payload(
    identity: DeviceIdentity,
    enrollment_code: str,
) -> dict[str, Any]:
    return {
        "device_id": identity.device_id,
        "enrollment_code": enrollment_code,
        "device_fingerprint_snapshot": _device_fingerprint_snapshot(identity),
    }


def build_revoke_device_link_payload(device_id: str) -> dict[str, str]:
    return {"device_id": device_id}


class AuditApiClient:
    def __init__(
        self,
        backend_url: str,
        *,
        agent_token: str,
        agent_token_header: str = "X-Agent-Token",
        timeout_seconds: int = 10,
        allow_insecure_transport: bool = False,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        _validate_backend_url_security(
            self._backend_url,
            allow_insecure_transport=allow_insecure_transport,
        )
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
        company_id: str,
        company_device_link_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.post_json(
            "/api/v1/audit/lifecycle-events",
            build_lifecycle_event_payload(
                identity,
                event_type,
                occurred_at,
                company_id=company_id,
                company_device_link_id=company_device_link_id,
                reason=reason,
            ),
        )

    def send_network_event(self, payload: dict[str, object]) -> dict[str, Any]:
        return self.post_json("/api/v1/audit/network-events", payload)

    def request_device_enrollment(
        self,
        identity: DeviceIdentity,
        enrollment_code: str,
    ) -> dict[str, Any]:
        return self.post_json(
            "/api/v1/companies/enrollment-requests",
            build_device_enrollment_payload(identity, enrollment_code),
        )

    def list_device_links(self, device_id: str) -> list[dict[str, Any]]:
        response = self.get_json(
            "/api/v1/companies/device-links",
            params={"device_id": device_id},
        )
        if not isinstance(response, list):
            raise AgentTransportError("Respuesta inesperada del backend para device-links")
        return [item for item in response if isinstance(item, dict)]

    def revoke_device_link(
        self,
        *,
        device_id: str,
        company_device_link_id: str,
    ) -> dict[str, Any]:
        return self.post_json(
            f"/api/v1/companies/device-links/{company_device_link_id}/revoke",
            build_revoke_device_link_payload(device_id),
        )

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            url=f"{self._backend_url}{path}{query}",
            headers={
                "User-Agent": f"the-all-seeing-eye-agent/{AGENT_VERSION}",
                self._agent_token_header: self._agent_token,
            },
            method="GET",
        )

        raw_response = self._open(request, path)
        if not raw_response:
            return {}
        return json.loads(raw_response.decode())

    def post_json(self, path: str, payload: dict[str, Any] | dict[str, object]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        request = Request(
            url=f"{self._backend_url}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"the-all-seeing-eye-agent/{AGENT_VERSION}",
                self._agent_token_header: self._agent_token,
            },
            method="POST",
        )

        raw_response = self._open(request, path)
        if not raw_response:
            return {}

        decoded = json.loads(raw_response.decode())
        if not isinstance(decoded, dict):
            raise AgentTransportError(f"Respuesta inesperada del backend para {path}")
        return decoded

    def _open(self, request: Request, path: str) -> bytes:
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            raise AgentTransportError(
                f"Backend respondio {exc.code} al enviar {path}: {error_body}",
                retryable=_is_retryable_http_status(exc.code),
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise AgentTransportError(f"No se pudo conectar con el backend: {exc.reason}") from exc


def _is_retryable_http_status(status_code: int) -> bool:
    return status_code == 408 or status_code == 429 or status_code >= 500


def _validate_backend_url_security(
    backend_url: str,
    *,
    allow_insecure_transport: bool,
) -> None:
    parsed_url = urlparse(backend_url)
    if parsed_url.scheme == "https":
        return
    if parsed_url.scheme != "http":
        raise InsecureBackendUrlError("AGENT_BACKEND_URL debe usar http o https")
    if allow_insecure_transport:
        return
    if parsed_url.hostname is not None and _is_loopback_host(parsed_url.hostname):
        return

    raise InsecureBackendUrlError(
        "AGENT_BACKEND_URL debe usar HTTPS para hosts no locales. "
        "Solo se permite HTTP no-local con AGENT_ALLOW_INSECURE_TRANSPORT=true.",
    )


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _device_fingerprint_snapshot(identity: DeviceIdentity) -> dict[str, str]:
    return {
        "hostname": identity.hostname,
        "os_name": identity.os_name,
        "agent_version": identity.agent_version,
        "primary_local_ip": identity.primary_local_ip or "",
        "primary_interface_name": identity.primary_interface_name or "",
        "primary_mac_address": identity.primary_mac_address or "",
    }
