from dataclasses import dataclass
from os import getenv

AGENT_VERSION = "0.1.0"


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value)


@dataclass(frozen=True, slots=True)
class AgentSettings:
    backend_url: str = "http://127.0.0.1:8000"
    device_id: str | None = None
    heartbeat_interval_seconds: int = 60
    scan_interval_seconds: int = 15
    network_event_dedup_seconds: int = 300
    request_timeout_seconds: int = 10

    @classmethod
    def from_environment(cls) -> "AgentSettings":
        device_id = getenv("AGENT_DEVICE_ID")
        if device_id is not None and device_id.strip() == "":
            device_id = None

        return cls(
            backend_url=getenv("AGENT_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/"),
            device_id=device_id,
            heartbeat_interval_seconds=_get_int("AGENT_HEARTBEAT_INTERVAL_SECONDS", 60),
            scan_interval_seconds=_get_int("AGENT_SCAN_INTERVAL_SECONDS", 15),
            network_event_dedup_seconds=_get_int("AGENT_NETWORK_EVENT_DEDUP_SECONDS", 300),
            request_timeout_seconds=_get_int("AGENT_REQUEST_TIMEOUT_SECONDS", 10),
        )

