from dataclasses import dataclass

from backend.app.companies.domain.repositories import (
    AuditorSessionRepository,
    CompanyDeviceLinkRepository,
    CompanyRepository,
    EnrollmentRequestRepository,
)
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import ensure_aware, utc_now


@dataclass(frozen=True, slots=True)
class QueryCompanySummaryCommand:
    company_id: str
    heartbeat_timeout_seconds: int


@dataclass(frozen=True, slots=True)
class CompanySummary:
    company_id: str
    name: str
    status: str
    linked_devices: int
    active_links: int
    connected_devices: int
    without_report_devices: int
    pending_enrollment_requests: int
    active_auditor_sessions: int


class QueryCompanySummaryUseCase:
    def __init__(
        self,
        company_repository: CompanyRepository,
        company_device_link_repository: CompanyDeviceLinkRepository,
        enrollment_request_repository: EnrollmentRequestRepository,
        auditor_session_repository: AuditorSessionRepository,
        device_repository: DeviceRepository,
    ) -> None:
        self._company_repository = company_repository
        self._company_device_link_repository = company_device_link_repository
        self._enrollment_request_repository = enrollment_request_repository
        self._auditor_session_repository = auditor_session_repository
        self._device_repository = device_repository

    def execute(self, command: QueryCompanySummaryCommand) -> CompanySummary:
        company = self._company_repository.find_by_id(command.company_id)
        if company is None:
            raise DomainValidationError("Empresa no encontrada")

        links = self._company_device_link_repository.list_by_company(command.company_id)
        active_links = [link for link in links if link.is_active]
        stale_after_seconds = max(command.heartbeat_timeout_seconds, 1)
        now = utc_now()
        connected_devices = 0
        without_report_devices = 0
        for link in active_links:
            device = self._device_repository.find_by_id(link.device_id)
            if device is None or device.last_seen_at is None:
                without_report_devices += 1
                continue
            elapsed_seconds = (now - ensure_aware(device.last_seen_at)).total_seconds()
            if elapsed_seconds <= stale_after_seconds:
                connected_devices += 1
            else:
                without_report_devices += 1

        pending_requests = self._enrollment_request_repository.list_by_company(
            company_id=command.company_id,
            status="PENDING",
        )
        active_sessions = [
            session
            for session in self._auditor_session_repository.list_active_by_company(
                command.company_id,
            )
            if session.is_active(now)
        ]
        return CompanySummary(
            company_id=company.company_id,
            name=company.name,
            status=company.status.value,
            linked_devices=len(links),
            active_links=len(active_links),
            connected_devices=connected_devices,
            without_report_devices=without_report_devices,
            pending_enrollment_requests=len(pending_requests),
            active_auditor_sessions=len(active_sessions),
        )
