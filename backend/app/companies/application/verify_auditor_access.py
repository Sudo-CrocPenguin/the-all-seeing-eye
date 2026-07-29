from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from backend.app.companies.application.secret_hasher import SecretHasher
from backend.app.companies.domain.entities import (
    AuditorAccessRequestStatus,
    AuditorSession,
)
from backend.app.companies.domain.repositories import (
    AuditorAccessRequestRepository,
    AuditorSessionRepository,
)
from backend.app.shared.time import utc_now

DEFAULT_AUDITOR_SCOPES = (
    "company:read",
    "devices:read",
    "devices:approve",
    "audit:read",
    "audit:export_json",
)
DEFAULT_MAX_OTP_FAILED_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class VerifyAuditorAccessCommand:
    auditor_access_request_id: str
    company_id: str
    device_id: str
    verification_code: str
    session_ttl_seconds: int = 43_200
    max_failed_attempts: int = DEFAULT_MAX_OTP_FAILED_ATTEMPTS


@dataclass(frozen=True, slots=True)
class VerifyAuditorAccessResult:
    session: AuditorSession | None = None
    error_detail: str | None = None

    @property
    def is_success(self) -> bool:
        return self.session is not None


class VerifyAuditorAccessUseCase:
    def __init__(
        self,
        access_request_repository: AuditorAccessRequestRepository,
        auditor_session_repository: AuditorSessionRepository,
        secret_hasher: SecretHasher | None = None,
    ) -> None:
        self._access_request_repository = access_request_repository
        self._auditor_session_repository = auditor_session_repository
        self._secret_hasher = secret_hasher or SecretHasher()

    def execute(self, command: VerifyAuditorAccessCommand) -> VerifyAuditorAccessResult:
        access_request = self._access_request_repository.find_by_id(
            command.auditor_access_request_id,
        )
        if access_request is None:
            return VerifyAuditorAccessResult(error_detail="Solicitud de auditor no encontrada")
        if access_request.company_id != command.company_id:
            return VerifyAuditorAccessResult(
                error_detail="La solicitud no pertenece a esta empresa",
            )
        if access_request.device_id != command.device_id:
            return VerifyAuditorAccessResult(
                error_detail="La solicitud no pertenece a este dispositivo",
            )

        verified_at = utc_now()
        if access_request.status == AuditorAccessRequestStatus.VERIFIED:
            return VerifyAuditorAccessResult(
                error_detail="La solicitud de auditor ya fue verificada",
            )
        if access_request.status == AuditorAccessRequestStatus.DENIED:
            return VerifyAuditorAccessResult(error_detail="La solicitud de auditor fue denegada")
        if access_request.status == AuditorAccessRequestStatus.EXPIRED:
            return VerifyAuditorAccessResult(error_detail="La solicitud de auditor expiro")
        if not access_request.is_pending(verified_at):
            access_request.mark_expired()
            self._access_request_repository.save(access_request)
            return VerifyAuditorAccessResult(
                error_detail="La solicitud de auditor no esta vigente",
            )

        if not self._secret_hasher.verify(
            command.verification_code,
            expected_hash=access_request.otp_hash,
            secret_salt=access_request.otp_salt,
        ):
            was_blocked = access_request.register_failed_attempt(
                max_failed_attempts=command.max_failed_attempts,
            )
            self._access_request_repository.save(access_request)
            if was_blocked:
                return VerifyAuditorAccessResult(
                    error_detail=(
                        "La solicitud de auditor fue bloqueada por intentos fallidos"
                    ),
                )
            return VerifyAuditorAccessResult(error_detail="Codigo SMS invalido")

        session = AuditorSession(
            auditor_session_id=str(uuid4()),
            company_id=command.company_id,
            device_id=command.device_id,
            created_at=verified_at,
            expires_at=verified_at + timedelta(seconds=max(command.session_ttl_seconds, 60)),
            scopes=DEFAULT_AUDITOR_SCOPES,
        )
        saved_session = self._auditor_session_repository.save(session)
        access_request.mark_verified(saved_session.auditor_session_id, verified_at)
        self._access_request_repository.save(access_request)
        return VerifyAuditorAccessResult(session=saved_session)
