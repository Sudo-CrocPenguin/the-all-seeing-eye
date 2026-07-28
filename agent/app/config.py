from dataclasses import dataclass
from os import getenv
from pathlib import Path

from agent.app.env_file import load_agent_environment

AGENT_VERSION = "0.1.0"


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value)


def _get_path(name: str) -> Path | None:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None
    return Path(raw_value.strip())


@dataclass(frozen=True, slots=True)
class AgentSettings:
    backend_url: str = "http://127.0.0.1:8000"
    device_id: str | None = None
    agent_token: str | None = None
    agent_token_header: str = "X-Agent-Token"
    heartbeat_interval_seconds: int = 60
    scan_interval_seconds: int = 15
    network_event_dedup_seconds: int = 300
    request_timeout_seconds: int = 10
    request_retry_backoff_seconds: int = 30
    queue_file: Path = Path.home() / ".local/state/the-all-seeing-eye/agent-queue.jsonl"
    service_map_file: Path | None = None

    @classmethod
    def from_environment(cls, env_file: str | Path | None = None) -> "AgentSettings":
        load_agent_environment(env_file)
        device_id = getenv("AGENT_DEVICE_ID")
        if device_id is not None and device_id.strip() == "":
            device_id = None

        return cls(
            backend_url=getenv("AGENT_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/"),
            device_id=device_id,
            agent_token=_normalize_optional_text(getenv("AGENT_TOKEN")),
            agent_token_header=getenv("AGENT_TOKEN_HEADER", "X-Agent-Token"),
            heartbeat_interval_seconds=_get_int("AGENT_HEARTBEAT_INTERVAL_SECONDS", 60),
            scan_interval_seconds=_get_int("AGENT_SCAN_INTERVAL_SECONDS", 15),
            network_event_dedup_seconds=_get_int("AGENT_NETWORK_EVENT_DEDUP_SECONDS", 300),
            request_timeout_seconds=_get_int("AGENT_REQUEST_TIMEOUT_SECONDS", 10),
            request_retry_backoff_seconds=_get_int("AGENT_REQUEST_RETRY_BACKOFF_SECONDS", 30),
            queue_file=Path(
                getenv(
                    "AGENT_QUEUE_FILE",
                    str(Path.home() / ".local/state/the-all-seeing-eye/agent-queue.jsonl"),
                ),
            ),
            service_map_file=_get_path("AGENT_SERVICE_MAP_FILE"),
        )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
