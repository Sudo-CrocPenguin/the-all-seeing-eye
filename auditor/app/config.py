from dataclasses import dataclass
from os import getenv
from pathlib import Path

from agent.app.env_file import load_agent_environment


def _get_int(name: str, default: int) -> int:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value)


def _get_bool(name: str, default: bool) -> bool:
    raw_value = getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on", "si"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} debe ser booleano")


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True, slots=True)
class AuditorSettings:
    backend_url: str = "http://127.0.0.1:8000"
    device_id: str | None = None
    agent_token: str | None = None
    agent_token_header: str = "X-Agent-Token"
    auditor_session_header: str = "X-Auditor-Session"
    request_timeout_seconds: int = 10
    session_file: Path = Path.home() / ".local/state/the-all-seeing-eye/auditor-session.json"
    allow_insecure_transport: bool = False

    @classmethod
    def from_environment(cls, env_file: str | Path | None = None) -> "AuditorSettings":
        load_agent_environment(env_file)
        return cls(
            backend_url=getenv(
                "AUDITOR_BACKEND_URL",
                getenv("AGENT_BACKEND_URL", "http://127.0.0.1:8000"),
            ).rstrip("/"),
            device_id=_normalize_optional_text(
                getenv("AUDITOR_DEVICE_ID", getenv("AGENT_DEVICE_ID")),
            ),
            agent_token=_normalize_optional_text(
                getenv("AUDITOR_AGENT_TOKEN", getenv("AGENT_TOKEN")),
            ),
            agent_token_header=getenv(
                "AUDITOR_AGENT_TOKEN_HEADER",
                getenv("AGENT_TOKEN_HEADER", "X-Agent-Token"),
            ),
            auditor_session_header=getenv("AUDITOR_SESSION_HEADER", "X-Auditor-Session"),
            request_timeout_seconds=_get_int(
                "AUDITOR_REQUEST_TIMEOUT_SECONDS",
                _get_int("AGENT_REQUEST_TIMEOUT_SECONDS", 10),
            ),
            session_file=Path(
                getenv(
                    "AUDITOR_SESSION_FILE",
                    str(
                        Path.home()
                        / ".local/state/the-all-seeing-eye/auditor-session.json",
                    ),
                ),
            ),
            allow_insecure_transport=_get_bool(
                "AUDITOR_ALLOW_INSECURE_TRANSPORT",
                _get_bool("AGENT_ALLOW_INSECURE_TRANSPORT", False),
            ),
        )
