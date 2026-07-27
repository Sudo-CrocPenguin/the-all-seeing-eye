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
class AgentCredential:
    device_id: str
    token_hash: str
    token_salt: str
    created_at: datetime = field(default_factory=utc_now)
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        self.device_id = _require_text(self.device_id, "device_id")
        self.token_hash = _require_text(self.token_hash, "token_hash")
        self.token_salt = _require_text(self.token_salt, "token_salt")
        self.created_at = ensure_aware(self.created_at)
        if self.last_used_at is not None:
            self.last_used_at = ensure_aware(self.last_used_at)
        if self.revoked_at is not None:
            self.revoked_at = ensure_aware(self.revoked_at)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def mark_used(self, used_at: datetime | None = None) -> None:
        self.last_used_at = ensure_aware(used_at or utc_now())

    def revoke(self, revoked_at: datetime | None = None) -> None:
        self.revoked_at = ensure_aware(revoked_at or utc_now())

