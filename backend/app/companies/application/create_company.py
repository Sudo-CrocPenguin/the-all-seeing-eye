from dataclasses import dataclass
from uuid import uuid4

from backend.app.companies.domain.entities import Company
from backend.app.companies.domain.repositories import CompanyRepository
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class CreateCompanyCommand:
    name: str
    phone_number: str


class CreateCompanyUseCase:
    def __init__(self, repository: CompanyRepository) -> None:
        self._repository = repository

    def execute(self, command: CreateCompanyCommand) -> Company:
        company = Company(
            company_id=str(uuid4()),
            name=command.name,
            phone_number=command.phone_number,
            created_at=utc_now(),
        )
        return self._repository.save(company)

