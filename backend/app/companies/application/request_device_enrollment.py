from dataclasses import dataclass, field
from uuid import uuid4

from backend.app.companies.application.secret_hasher import SecretHasher
from backend.app.companies.domain.entities import EnrollmentRequest
from backend.app.companies.domain.repositories import (
    CompanyDeviceLinkRepository,
    EnrollmentCodeRepository,
    EnrollmentRequestRepository,
)
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class RequestDeviceEnrollmentCommand:
    device_id: str
    enrollment_code: str
    device_fingerprint_snapshot: dict[str, str] = field(default_factory=dict)


class RequestDeviceEnrollmentUseCase:
    def __init__(
        self,
        enrollment_code_repository: EnrollmentCodeRepository,
        enrollment_request_repository: EnrollmentRequestRepository,
        company_device_link_repository: CompanyDeviceLinkRepository,
        secret_hasher: SecretHasher | None = None,
    ) -> None:
        self._enrollment_code_repository = enrollment_code_repository
        self._enrollment_request_repository = enrollment_request_repository
        self._company_device_link_repository = company_device_link_repository
        self._secret_hasher = secret_hasher or SecretHasher()

    def execute(self, command: RequestDeviceEnrollmentCommand) -> EnrollmentRequest:
        code_digest = self._secret_hasher.digest_secret(command.enrollment_code)
        enrollment_code = self._enrollment_code_repository.find_by_code_digest(code_digest)
        if enrollment_code is None:
            raise DomainValidationError("Codigo de vinculacion invalido")
        if not enrollment_code.is_active():
            raise DomainValidationError("Codigo de vinculacion expirado o sin usos")
        if not self._secret_hasher.verify(
            command.enrollment_code,
            expected_hash=enrollment_code.code_hash,
            secret_salt=enrollment_code.code_salt,
        ):
            raise DomainValidationError("Codigo de vinculacion invalido")

        active_link = self._company_device_link_repository.find_active_by_company_and_device(
            company_id=enrollment_code.company_id,
            device_id=command.device_id,
        )
        if active_link is not None:
            raise DomainValidationError("El dispositivo ya esta vinculado a esta empresa")

        pending_request = self._enrollment_request_repository.find_pending_by_company_and_device(
            company_id=enrollment_code.company_id,
            device_id=command.device_id,
        )
        if pending_request is not None:
            return pending_request

        enrollment_code.register_use()
        self._enrollment_code_repository.save(enrollment_code)
        enrollment_request = EnrollmentRequest(
            enrollment_request_id=str(uuid4()),
            company_id=enrollment_code.company_id,
            device_id=command.device_id,
            requested_at=utc_now(),
            device_fingerprint_snapshot=dict(command.device_fingerprint_snapshot),
        )
        return self._enrollment_request_repository.save(enrollment_request)

