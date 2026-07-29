from dataclasses import dataclass, field
from datetime import datetime

from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import ensure_aware, utc_now


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} es obligatorio")
    return normalized


@dataclass(slots=True)
class Device:
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    registered_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.device_id = _require_text(self.device_id, "device_id")
        self.hostname = _require_text(self.hostname, "hostname")
        self.os_name = _require_text(self.os_name, "os_name")
        self.agent_version = _require_text(self.agent_version, "agent_version")
        self.registered_at = ensure_aware(self.registered_at)
        if self.last_seen_at is not None:
            self.last_seen_at = ensure_aware(self.last_seen_at)

    def mark_seen(self, seen_at: datetime | None = None) -> None:
        self.last_seen_at = ensure_aware(seen_at or utc_now())

