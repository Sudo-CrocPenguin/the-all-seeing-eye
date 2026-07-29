from dataclasses import dataclass

from backend.app.companies.domain.entities import CompanyDeviceLink
from backend.app.companies.domain.repositories import CompanyDeviceLinkRepository
from backend.app.shared.domain import DomainValidationError


@dataclass(frozen=True, slots=True)
class RevokeDeviceCompanyLinkCommand:
    device_id: str
    company_device_link_id: str


class RevokeDeviceCompanyLinkUseCase:
    def __init__(self, company_device_link_repository: CompanyDeviceLinkRepository) -> None:
        self._company_device_link_repository = company_device_link_repository

    def execute(self, command: RevokeDeviceCompanyLinkCommand) -> CompanyDeviceLink:
        link = self._company_device_link_repository.find_by_id(
            command.company_device_link_id,
        )
        if link is None:
            raise DomainValidationError("Vinculo empresa-dispositivo no encontrado")
        if link.device_id != command.device_id:
            raise DomainValidationError("El vinculo no pertenece a este dispositivo")
        if link.is_active:
            link.revoke_by_device()
            return self._company_device_link_repository.save(link)
        return link
