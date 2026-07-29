import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditorStateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AuditorSessionState:
    auditor_session_id: str
    company_id: str
    device_id: str
    expires_at: str
    scopes: tuple[str, ...] = field(default_factory=tuple)
    created_at: str | None = None
    revoked_at: str | None = None

    @classmethod
    def from_json(cls, raw_value: dict[str, Any]) -> "AuditorSessionState":
        raw_scopes = raw_value.get("scopes", [])
        if not isinstance(raw_scopes, list) or not all(
            isinstance(scope, str) for scope in raw_scopes
        ):
            raise AuditorStateError("scopes debe ser una lista de textos")

        return cls(
            auditor_session_id=_required_text(raw_value, "auditor_session_id"),
            company_id=_required_text(raw_value, "company_id"),
            device_id=_required_text(raw_value, "device_id"),
            expires_at=_required_text(raw_value, "expires_at"),
            scopes=tuple(scope.strip() for scope in raw_scopes if scope.strip()),
            created_at=_optional_text(raw_value, "created_at"),
            revoked_at=_optional_text(raw_value, "revoked_at"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "auditor_session_id": self.auditor_session_id,
            "company_id": self.company_id,
            "device_id": self.device_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "scopes": list(self.scopes),
            "revoked_at": self.revoked_at,
        }

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, now: datetime | None = None) -> bool:
        expires_at = _parse_datetime(self.expires_at)
        current_time = now or datetime.now(UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        return expires_at <= current_time


class JsonAuditorSessionStore:
    def __init__(self, session_file: Path) -> None:
        self._session_file = session_file

    @property
    def session_file(self) -> Path:
        return self._session_file

    def load(self) -> AuditorSessionState | None:
        if not self._session_file.exists():
            return None
        try:
            raw_value = json.loads(self._session_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuditorStateError(f"Sesion local invalida en {self._session_file}") from exc
        if not isinstance(raw_value, dict):
            raise AuditorStateError("La sesion local debe ser un objeto JSON")
        return AuditorSessionState.from_json(raw_value)

    def save(self, session: AuditorSessionState) -> AuditorSessionState:
        self._session_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self._session_file.with_suffix(f"{self._session_file.suffix}.tmp")
        temporary_file.write_text(
            json.dumps(session.to_json(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_file.replace(self._session_file)
        return session

    def clear(self) -> None:
        if self._session_file.exists():
            self._session_file.unlink()


def auditor_session_from_response(raw_value: dict[str, Any]) -> AuditorSessionState:
    return AuditorSessionState.from_json(raw_value)


def _required_text(raw_value: dict[str, Any], field_name: str) -> str:
    value = _optional_text(raw_value, field_name)
    if value is None:
        raise AuditorStateError(f"{field_name} es obligatorio")
    return value


def _optional_text(raw_value: dict[str, Any], field_name: str) -> str | None:
    value = raw_value.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AuditorStateError(f"{field_name} debe ser texto")
    normalized = value.strip()
    return normalized or None


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AuditorStateError(f"Fecha invalida en sesion local: {value}") from exc
