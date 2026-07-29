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
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now

DEFAULT_AUDITOR_SCOPES = (
    "company:read",
    "devices:read",
    "devices:approve",
    "audit:read",
    "audit:export_json",
)


@dataclass(frozen=True, slots=True)
class VerifyAuditorAccessCommand:
    auditor_access_request_id: str
    company_id: str
    device_id: str
    verification_code: str
    session_ttl_seconds: int = 43_200


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

    def execute(self, command: VerifyAuditorAccessCommand) -> AuditorSession:
        access_request = self._access_request_repository.find_by_id(
            command.auditor_access_request_id,
        )
        if access_request is None:
            raise DomainValidationError("Solicitud de auditor no encontrada")
        if access_request.company_id != command.company_id:
            raise DomainValidationError("La solicitud no pertenece a esta empresa")
        if access_request.device_id != command.device_id:
            raise DomainValidationError("La solicitud no pertenece a este dispositivo")

        verified_at = utc_now()
        if access_request.status is AuditorAccessRequestStatus.VERIFIED:
            raise DomainValidationError("La solicitud de auditor ya fue verificada")
        if access_request.status is AuditorAccessRequestStatus.DENIED:
            raise DomainValidationError("La solicitud de auditor fue denegada")
        if access_request.status is AuditorAccessRequestStatus.EXPIRED:
            raise DomainValidationError("La solicitud de auditor expiro")
        if not access_request.is_pending(verified_at):
            access_request.mark_expired()
            self._access_request_repository.save(access_request)
            raise DomainValidationError("La solicitud de auditor no esta vigente")

        if not self._secret_hasher.verify(
            command.verification_code,
            expected_hash=access_request.otp_hash,
            secret_salt=access_request.otp_salt,
        ):
            access_request.register_failed_attempt()
            self._access_request_repository.save(access_request)
            raise DomainValidationError("Codigo SMS invalido")

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
        return saved_session
