import json
from ipaddress import ip_address
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from agent.app.config import AGENT_VERSION


class InsecureAuditorBackendUrlError(ValueError):
    pass


class AuditorTransportError(RuntimeError):
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


class AuditorApiClient:
    def __init__(
        self,
        backend_url: str,
        *,
        agent_token: str | None = None,
        agent_token_header: str = "X-Agent-Token",
        auditor_session_header: str = "X-Auditor-Session",
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
        self._auditor_session_header = auditor_session_header
        self._timeout_seconds = timeout_seconds

    def create_company(self, *, name: str, phone_number: str) -> dict[str, Any]:
        return self.post_json(
            "/api/v1/companies",
            {"name": name, "phone_number": phone_number},
        )

    def request_auditor_access(self, *, company_id: str, device_id: str) -> dict[str, Any]:
        return self.post_json(
            f"/api/v1/companies/{company_id}/auditor-access-requests",
            {"device_id": device_id},
            headers=self._agent_headers(),
        )

    def verify_auditor_access(
        self,
        *,
        company_id: str,
        auditor_access_request_id: str,
        device_id: str,
        verification_code: str,
    ) -> dict[str, Any]:
        return self.post_json(
            (
                f"/api/v1/companies/{company_id}/auditor-access-requests/"
                f"{auditor_access_request_id}/verify"
            ),
            {"device_id": device_id, "verification_code": verification_code},
            headers=self._agent_headers(),
        )

    def create_enrollment_code(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        ttl_seconds: int,
        max_uses: int,
    ) -> dict[str, Any]:
        return self.post_json(
            f"/api/v1/companies/{company_id}/enrollment-codes",
            {"ttl_seconds": ttl_seconds, "max_uses": max_uses},
            headers=self._auditor_headers(auditor_session_id),
        )

    def list_enrollment_requests(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        response = self.get_json(
            f"/api/v1/companies/{company_id}/enrollment-requests",
            params={"status": status_filter},
            headers=self._auditor_headers(auditor_session_id),
        )
        return _require_list_response(response, "enrollment-requests")

    def review_enrollment_request(
        self,
        *,
        company_id: str,
        enrollment_request_id: str,
        auditor_session_id: str,
        decision: str,
    ) -> dict[str, Any]:
        return self.post_json(
            f"/api/v1/companies/{company_id}/enrollment-requests/{enrollment_request_id}/review",
            {"decision": decision},
            headers=self._auditor_headers(auditor_session_id),
        )

    def get_company_summary(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
    ) -> dict[str, Any]:
        return self.get_object(
            f"/api/v1/companies/{company_id}/summary",
            headers=self._auditor_headers(auditor_session_id),
        )

    def search_network_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        response = self.get_json(
            "/api/v1/audit/network-events",
            params=filters,
            headers=self._auditor_headers(auditor_session_id),
        )
        return _require_list_response(response, "network-events")

    def search_lifecycle_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        response = self.get_json(
            "/api/v1/audit/lifecycle-events",
            params=filters,
            headers=self._auditor_headers(auditor_session_id),
        )
        return _require_list_response(response, "lifecycle-events")

    def search_device_movements(
        self,
        *,
        auditor_session_id: str,
        device_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        params = {"device_id": device_id, **filters}
        response = self.get_json(
            "/api/v1/audit/device-movements",
            params=params,
            headers=self._auditor_headers(auditor_session_id),
        )
        return _require_list_response(response, "device-movements")

    def query_incident_window(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> dict[str, Any]:
        return self.get_object(
            "/api/v1/audit/incident-window",
            params=filters,
            headers=self._auditor_headers(auditor_session_id),
        )

    def get_object(
        self,
        path: str,
        *,
        params: dict[str, object | None] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self.get_json(path, params=params, headers=headers)
        if not isinstance(response, dict):
            raise AuditorTransportError(f"Respuesta inesperada del backend para {path}")
        return response

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, object | None] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        query = f"?{urlencode(_clean_params(params))}" if params else ""
        request = Request(
            url=f"{self._backend_url}{path}{query}",
            headers=self._base_headers(headers),
            method="GET",
        )
        raw_response = self._open(request, path)
        if not raw_response:
            return {}
        return json.loads(raw_response.decode())

    def post_json(
        self,
        path: str,
        payload: dict[str, Any] | dict[str, object],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        request = Request(
            url=f"{self._backend_url}{path}",
            data=body,
            headers=self._base_headers({"Content-Type": "application/json", **(headers or {})}),
            method="POST",
        )
        raw_response = self._open(request, path)
        if not raw_response:
            return {}
        decoded = json.loads(raw_response.decode())
        if not isinstance(decoded, dict):
            raise AuditorTransportError(f"Respuesta inesperada del backend para {path}")
        return decoded

    def _base_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        return {
            "User-Agent": f"the-all-seeing-eye-auditor/{AGENT_VERSION}",
            **(extra_headers or {}),
        }

    def _agent_headers(self) -> dict[str, str]:
        if not self._agent_token:
            raise AuditorTransportError("AUDITOR_AGENT_TOKEN o AGENT_TOKEN es obligatorio")
        return {self._agent_token_header: self._agent_token}

    def _auditor_headers(self, auditor_session_id: str) -> dict[str, str]:
        return {self._auditor_session_header: auditor_session_id}

    def _open(self, request: Request, path: str) -> bytes:
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw_response = response.read()
                if not isinstance(raw_response, bytes):
                    raise AuditorTransportError(f"Respuesta inesperada del backend para {path}")
                return raw_response
        except HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            raise AuditorTransportError(
                f"Backend respondio {exc.code} al consultar {path}: {error_body}",
                retryable=_is_retryable_http_status(exc.code),
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise AuditorTransportError(
                f"No se pudo conectar con el backend: {exc.reason}",
            ) from exc


def _clean_params(params: dict[str, object | None] | None) -> dict[str, str]:
    if params is None:
        return {}
    return {
        key: str(value)
        for key, value in params.items()
        if value is not None and str(value).strip() != ""
    }


def _require_list_response(response: Any, response_name: str) -> list[dict[str, Any]]:
    if not isinstance(response, list):
        raise AuditorTransportError(f"Respuesta inesperada del backend para {response_name}")
    return [item for item in response if isinstance(item, dict)]


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
        raise InsecureAuditorBackendUrlError("AUDITOR_BACKEND_URL debe usar http o https")
    if allow_insecure_transport:
        return
    if parsed_url.hostname is not None and _is_loopback_host(parsed_url.hostname):
        return

    raise InsecureAuditorBackendUrlError(
        "AUDITOR_BACKEND_URL debe usar HTTPS para hosts no locales. "
        "Solo se permite HTTP no-local con AUDITOR_ALLOW_INSECURE_TRANSPORT=true.",
    )


def _is_loopback_host(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False
