from dataclasses import dataclass
from datetime import datetime

from backend.app.companies.domain.entities import CompanyDeviceLink
from backend.app.companies.domain.repositories import (
    CompanyDeviceLinkRepository,
    CompanyRepository,
)


@dataclass(frozen=True, slots=True)
class QueryDeviceCompanyLinksCommand:
    device_id: str


@dataclass(frozen=True, slots=True)
class DeviceCompanyLink:
    company_device_link_id: str
    company_id: str
    company_name: str
    device_id: str
    linked_at: datetime
    status: str
    revoked_at: datetime | None
    revoked_by_device: bool
    revoked_by_auditor_session_id: str | None


class QueryDeviceCompanyLinksUseCase:
    def __init__(
        self,
        company_device_link_repository: CompanyDeviceLinkRepository,
        company_repository: CompanyRepository,
    ) -> None:
        self._company_device_link_repository = company_device_link_repository
        self._company_repository = company_repository

    def execute(self, command: QueryDeviceCompanyLinksCommand) -> list[DeviceCompanyLink]:
        links = self._company_device_link_repository.list_by_device(command.device_id)
        return [self._to_result(link) for link in links]

    def _to_result(self, link: CompanyDeviceLink) -> DeviceCompanyLink:
        company = self._company_repository.find_by_id(link.company_id)
        return DeviceCompanyLink(
            company_device_link_id=link.company_device_link_id,
            company_id=link.company_id,
            company_name=company.name if company is not None else link.company_id,
            device_id=link.device_id,
            linked_at=link.linked_at,
            status=link.status.value,
            revoked_at=link.revoked_at,
            revoked_by_device=link.revoked_by_device,
            revoked_by_auditor_session_id=link.revoked_by_auditor_session_id,
        )
