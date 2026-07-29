from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from backend.app.companies.application.secret_hasher import SecretHasher
from backend.app.companies.domain.entities import EnrollmentCode
from backend.app.companies.domain.repositories import CompanyRepository, EnrollmentCodeRepository
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class CreateEnrollmentCodeCommand:
    company_id: str
    ttl_seconds: int = 86_400
    max_uses: int = 1


@dataclass(frozen=True, slots=True)
class CreatedEnrollmentCode:
    enrollment_code: EnrollmentCode
    code: str


class CreateEnrollmentCodeUseCase:
    def __init__(
        self,
        company_repository: CompanyRepository,
        enrollment_code_repository: EnrollmentCodeRepository,
        secret_hasher: SecretHasher | None = None,
    ) -> None:
        self._company_repository = company_repository
        self._enrollment_code_repository = enrollment_code_repository
        self._secret_hasher = secret_hasher or SecretHasher()

    def execute(self, command: CreateEnrollmentCodeCommand) -> CreatedEnrollmentCode:
        company = self._company_repository.find_by_id(command.company_id)
        if company is None or not company.is_active:
            raise DomainValidationError("Empresa no encontrada o inactiva")

        code = self._secret_hasher.generate_enrollment_code()
        hashed_code = self._secret_hasher.hash_secret(code)
        created_at = utc_now()
        enrollment_code = EnrollmentCode(
            enrollment_code_id=str(uuid4()),
            company_id=command.company_id,
            code_digest=self._secret_hasher.digest_secret(code),
            code_hash=hashed_code.secret_hash,
            code_salt=hashed_code.secret_salt,
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=max(command.ttl_seconds, 60)),
            max_uses=max(command.max_uses, 1),
        )
        saved_code = self._enrollment_code_repository.save(enrollment_code)
        return CreatedEnrollmentCode(enrollment_code=saved_code, code=code)

