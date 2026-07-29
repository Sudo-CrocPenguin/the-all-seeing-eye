from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import ensure_aware, utc_now


class CompanyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class EnrollmentRequestStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"


class CompanyDeviceLinkStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    REVOKED = "REVOKED"


class AuditorAccessRequestStatus(StrEnum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    DENIED = "DENIED"


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


def _validate_positive(value: int, field_name: str) -> int:
    if value < 1:
        raise DomainValidationError(f"{field_name} debe ser mayor que cero")
    return value


@dataclass(slots=True)
class Company:
    company_id: str
    name: str
    phone_number: str
    created_at: datetime = field(default_factory=utc_now)
    status: CompanyStatus = CompanyStatus.ACTIVE

    def __post_init__(self) -> None:
        self.company_id = _require_text(self.company_id, "company_id")
        self.name = _require_text(self.name, "name")
        self.phone_number = _require_text(self.phone_number, "phone_number")
        self.created_at = ensure_aware(self.created_at)
        self.status = CompanyStatus(self.status)

    @property
    def is_active(self) -> bool:
        return self.status is CompanyStatus.ACTIVE


@dataclass(slots=True)
class EnrollmentCode:
    enrollment_code_id: str
    company_id: str
    code_digest: str
    code_hash: str
    code_salt: str
    created_at: datetime
    expires_at: datetime
    max_uses: int = 1
    used_count: int = 0
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        self.enrollment_code_id = _require_text(
            self.enrollment_code_id,
            "enrollment_code_id",
        )
        self.company_id = _require_text(self.company_id, "company_id")
        self.code_digest = _require_text(self.code_digest, "code_digest")
        self.code_hash = _require_text(self.code_hash, "code_hash")
        self.code_salt = _require_text(self.code_salt, "code_salt")
        self.created_at = ensure_aware(self.created_at)
        self.expires_at = ensure_aware(self.expires_at)
        self.max_uses = _validate_positive(self.max_uses, "max_uses")
        if self.used_count < 0:
            raise DomainValidationError("used_count no puede ser negativo")
        if self.revoked_at is not None:
            self.revoked_at = ensure_aware(self.revoked_at)

    def is_active(self, now: datetime | None = None) -> bool:
        checked_at = ensure_aware(now or utc_now())
        return (
            self.revoked_at is None
            and checked_at <= self.expires_at
            and self.used_count < self.max_uses
        )

    def register_use(self) -> None:
        if self.used_count >= self.max_uses:
            raise DomainValidationError("El codigo de vinculacion ya no tiene usos disponibles")
        self.used_count += 1


@dataclass(slots=True)
class EnrollmentRequest:
    enrollment_request_id: str
    company_id: str
    device_id: str
    requested_at: datetime
    status: EnrollmentRequestStatus = EnrollmentRequestStatus.PENDING
    reviewed_by_auditor_session_id: str | None = None
    reviewed_at: datetime | None = None
    device_fingerprint_snapshot: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.enrollment_request_id = _require_text(
            self.enrollment_request_id,
            "enrollment_request_id",
        )
        self.company_id = _require_text(self.company_id, "company_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.requested_at = ensure_aware(self.requested_at)
        self.status = EnrollmentRequestStatus(self.status)
        self.reviewed_by_auditor_session_id = _normalize_optional_text(
            self.reviewed_by_auditor_session_id,
        )
        if self.reviewed_at is not None:
            self.reviewed_at = ensure_aware(self.reviewed_at)

    @property
    def is_pending(self) -> bool:
        return self.status is EnrollmentRequestStatus.PENDING

    def accept(self, auditor_session_id: str, reviewed_at: datetime | None = None) -> None:
        self._ensure_pending()
        self.status = EnrollmentRequestStatus.ACCEPTED
        self.reviewed_by_auditor_session_id = _require_text(
            auditor_session_id,
            "auditor_session_id",
        )
        self.reviewed_at = ensure_aware(reviewed_at or utc_now())

    def deny(self, auditor_session_id: str, reviewed_at: datetime | None = None) -> None:
        self._ensure_pending()
        self.status = EnrollmentRequestStatus.DENIED
        self.reviewed_by_auditor_session_id = _require_text(
            auditor_session_id,
            "auditor_session_id",
        )
        self.reviewed_at = ensure_aware(reviewed_at or utc_now())

    def _ensure_pending(self) -> None:
        if not self.is_pending:
            raise DomainValidationError("La solicitud de vinculacion ya fue revisada")


@dataclass(slots=True)
class CompanyDeviceLink:
    company_device_link_id: str
    company_id: str
    device_id: str
    linked_at: datetime
    status: CompanyDeviceLinkStatus = CompanyDeviceLinkStatus.ACTIVE
    revoked_at: datetime | None = None
    revoked_by_device: bool = False
    revoked_by_auditor_session_id: str | None = None

    def __post_init__(self) -> None:
        self.company_device_link_id = _require_text(
            self.company_device_link_id,
            "company_device_link_id",
        )
        self.company_id = _require_text(self.company_id, "company_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.linked_at = ensure_aware(self.linked_at)
        self.status = CompanyDeviceLinkStatus(self.status)
        if self.revoked_at is not None:
            self.revoked_at = ensure_aware(self.revoked_at)
        self.revoked_by_auditor_session_id = _normalize_optional_text(
            self.revoked_by_auditor_session_id,
        )

    @property
    def is_active(self) -> bool:
        return self.status is CompanyDeviceLinkStatus.ACTIVE and self.revoked_at is None

    def revoke_by_device(self, revoked_at: datetime | None = None) -> None:
        self.status = CompanyDeviceLinkStatus.REVOKED
        self.revoked_at = ensure_aware(revoked_at or utc_now())
        self.revoked_by_device = True


@dataclass(slots=True)
class AuditorAccessRequest:
    auditor_access_request_id: str
    company_id: str
    device_id: str
    otp_hash: str
    otp_salt: str
    requested_at: datetime
    expires_at: datetime
    status: AuditorAccessRequestStatus = AuditorAccessRequestStatus.PENDING
    verified_at: datetime | None = None
    auditor_session_id: str | None = None
    failed_attempts: int = 0

    def __post_init__(self) -> None:
        self.auditor_access_request_id = _require_text(
            self.auditor_access_request_id,
            "auditor_access_request_id",
        )
        self.company_id = _require_text(self.company_id, "company_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.otp_hash = _require_text(self.otp_hash, "otp_hash")
        self.otp_salt = _require_text(self.otp_salt, "otp_salt")
        self.requested_at = ensure_aware(self.requested_at)
        self.expires_at = ensure_aware(self.expires_at)
        self.status = AuditorAccessRequestStatus(self.status)
        if self.verified_at is not None:
            self.verified_at = ensure_aware(self.verified_at)
        self.auditor_session_id = _normalize_optional_text(self.auditor_session_id)
        if self.failed_attempts < 0:
            raise DomainValidationError("failed_attempts no puede ser negativo")

    def is_pending(self, now: datetime | None = None) -> bool:
        checked_at = ensure_aware(now or utc_now())
        return self.status is AuditorAccessRequestStatus.PENDING and checked_at <= self.expires_at

    def register_failed_attempt(self) -> None:
        self.failed_attempts += 1

    def mark_verified(
        self,
        auditor_session_id: str,
        verified_at: datetime | None = None,
    ) -> None:
        self.status = AuditorAccessRequestStatus.VERIFIED
        self.verified_at = ensure_aware(verified_at or utc_now())
        self.auditor_session_id = _require_text(auditor_session_id, "auditor_session_id")

    def mark_expired(self) -> None:
        self.status = AuditorAccessRequestStatus.EXPIRED


@dataclass(slots=True)
class AuditorSession:
    auditor_session_id: str
    company_id: str
    device_id: str
    created_at: datetime
    expires_at: datetime
    scopes: tuple[str, ...]
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        self.auditor_session_id = _require_text(
            self.auditor_session_id,
            "auditor_session_id",
        )
        self.company_id = _require_text(self.company_id, "company_id")
        self.device_id = _require_text(self.device_id, "device_id")
        self.created_at = ensure_aware(self.created_at)
        self.expires_at = ensure_aware(self.expires_at)
        self.scopes = tuple(_require_text(scope, "scope") for scope in self.scopes)
        if self.revoked_at is not None:
            self.revoked_at = ensure_aware(self.revoked_at)

    def is_active(self, now: datetime | None = None) -> bool:
        checked_at = ensure_aware(now or utc_now())
        return self.revoked_at is None and checked_at <= self.expires_at

