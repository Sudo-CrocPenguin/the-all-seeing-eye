from dataclasses import dataclass

from backend.app.companies.domain.entities import CompanyDeviceLink
from backend.app.companies.domain.repositories import CompanyDeviceLinkRepository
from backend.app.shared.domain import DomainValidationError


@dataclass(frozen=True, slots=True)
class ResolveAuditCompanyContextCommand:
    company_id: str
    company_device_link_id: str
    device_id: str


class ResolveAuditCompanyContextUseCase:
    def __init__(self, company_device_link_repository: CompanyDeviceLinkRepository) -> None:
        self._company_device_link_repository = company_device_link_repository

    def execute(self, command: ResolveAuditCompanyContextCommand) -> CompanyDeviceLink:
        link = self._company_device_link_repository.find_by_id(
            command.company_device_link_id,
        )
        if link is None:
            raise DomainValidationError("Vinculo empresa-dispositivo no encontrado")
        if link.company_id != command.company_id:
            raise DomainValidationError("El vinculo no pertenece a esta empresa")
        if link.device_id != command.device_id:
            raise DomainValidationError("El vinculo no pertenece a este dispositivo")
        if not link.is_active:
            raise DomainValidationError("El vinculo empresa-dispositivo no esta activo")
        return link
