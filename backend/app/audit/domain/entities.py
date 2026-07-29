from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from ipaddress import ip_address

from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import ensure_aware, utc_now


class AgentLifecycleEventType(StrEnum):
    STARTED = "AGENT_STARTED"
    STOPPING = "AGENT_STOPPING"
    STOPPED = "AGENT_STOPPED"
    HEARTBEAT = "AGENT_HEARTBEAT"
    MISSED_HEARTBEAT = "AGENT_MISSED_HEARTBEAT"
    RECOVERED = "AGENT_RECOVERED"
    CONFIG_CHANGED = "AGENT_CONFIG_CHANGED"


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} es obligatorio")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_optional_ip(value: str | None, field_name: str) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    try:
        ip_address(normalized)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name} no es una IP valida") from exc
    return normalized


def _validate_optional_port(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 1 or value > 65535:
        raise DomainValidationError("destination_port debe estar entre 1 y 65535")
    return value


def _validate_non_negative(value: int, field_name: str) -> int:
    if value < 0:
        raise DomainValidationError(f"{field_name} no puede ser negativo")
    return value


def _validate_optional_non_negative(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    return _validate_non_negative(value, field_name)


@dataclass(slots=True)
class NetworkAuditEvent:
    event_id: str
    occurred_at: datetime
    device_id: str
    company_id: str
    company_device_link_id: str
    hostname: str
    os_name: str
    agent_version: str
    protocol: str
    local_ip: str | None = None
    public_ip: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    http_method: str | None = None
    http_status_code: int | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    network_interface: str | None = None
    mac_address: str | None = None
    local_username: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    process_executable: str | None = None
    service_name: str | None = None
    request_metadata: dict[str, str] = field(default_factory=dict)
    response_metadata: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.event_id = _require_text(self.event_id, "event_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.company_id = _require_text(self.company_id, "company_id")
        self.company_device_link_id = _require_text(
            self.company_device_link_id,
            "company_device_link_id",
        )
        self.hostname = _require_text(self.hostname, "hostname")
        self.os_name = _require_text(self.os_name, "os_name")
        self.agent_version = _require_text(self.agent_version, "agent_version")
        self.protocol = _require_text(self.protocol, "protocol").upper()
        self.occurred_at = ensure_aware(self.occurred_at)
        self.created_at = ensure_aware(self.created_at)
        self.local_ip = _validate_optional_ip(self.local_ip, "local_ip")
        self.public_ip = _validate_optional_ip(self.public_ip, "public_ip")
        self.destination_ip = _validate_optional_ip(self.destination_ip, "destination_ip")
        self.destination_port = _validate_optional_port(self.destination_port)
        self.destination_host = _normalize_optional_text(self.destination_host)
        self.http_method = _normalize_optional_text(self.http_method)
        if self.http_method is not None:
            self.http_method = self.http_method.upper()
        self.network_interface = _normalize_optional_text(self.network_interface)
        self.mac_address = _normalize_optional_text(self.mac_address)
        self.local_username = _normalize_optional_text(self.local_username)
        self.process_id = _validate_optional_non_negative(self.process_id, "process_id")
        self.process_name = _normalize_optional_text(self.process_name)
        self.process_executable = _normalize_optional_text(self.process_executable)
        self.service_name = _normalize_optional_text(self.service_name)
        self.bytes_sent = _validate_non_negative(self.bytes_sent, "bytes_sent")
        self.bytes_received = _validate_non_negative(self.bytes_received, "bytes_received")
        if self.http_status_code is not None and not 100 <= self.http_status_code <= 599:
            raise DomainValidationError("http_status_code debe estar entre 100 y 599")


@dataclass(slots=True)
class AgentLifecycleEvent:
    event_id: str
    event_type: AgentLifecycleEventType
    occurred_at: datetime
    device_id: str
    company_id: str
    company_device_link_id: str
    hostname: str
    agent_version: str
    local_ip: str | None = None
    public_ip: str | None = None
    reason: str | None = None
    last_seen_at: datetime | None = None
    detected_at: datetime | None = None
    downtime_seconds: int | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.event_id = _require_text(self.event_id, "event_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.company_id = _require_text(self.company_id, "company_id")
        self.company_device_link_id = _require_text(
            self.company_device_link_id,
            "company_device_link_id",
        )
        self.hostname = _require_text(self.hostname, "hostname")
        self.agent_version = _require_text(self.agent_version, "agent_version")
        self.event_type = AgentLifecycleEventType(self.event_type)
        self.occurred_at = ensure_aware(self.occurred_at)
        self.created_at = ensure_aware(self.created_at)
        self.local_ip = _validate_optional_ip(self.local_ip, "local_ip")
        self.public_ip = _validate_optional_ip(self.public_ip, "public_ip")
        self.reason = _normalize_optional_text(self.reason)
        if self.last_seen_at is not None:
            self.last_seen_at = ensure_aware(self.last_seen_at)
        if self.detected_at is not None:
            self.detected_at = ensure_aware(self.detected_at)
        if self.downtime_seconds is not None:
            self.downtime_seconds = _validate_non_negative(
                self.downtime_seconds,
                "downtime_seconds",
            )
