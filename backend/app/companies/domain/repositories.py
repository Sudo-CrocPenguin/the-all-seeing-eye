from datetime import datetime
from typing import Protocol

from backend.app.companies.domain.entities import (
    AuditorAccessRequest,
    AuditorOtpEvent,
    AuditorOtpEventType,
    AuditorSession,
    Company,
    CompanyDeviceLink,
    EnrollmentCode,
    EnrollmentRequest,
)


class CompanyRepository(Protocol):
    def save(self, company: Company) -> Company:
        raise NotImplementedError

    def find_by_id(self, company_id: str) -> Company | None:
        raise NotImplementedError

    def list_all(self) -> list[Company]:
        raise NotImplementedError


class EnrollmentCodeRepository(Protocol):
    def save(self, enrollment_code: EnrollmentCode) -> EnrollmentCode:
        raise NotImplementedError

    def find_by_id(self, enrollment_code_id: str) -> EnrollmentCode | None:
        raise NotImplementedError

    def find_by_code_digest(self, code_digest: str) -> EnrollmentCode | None:
        raise NotImplementedError


class EnrollmentRequestRepository(Protocol):
    def save(self, enrollment_request: EnrollmentRequest) -> EnrollmentRequest:
        raise NotImplementedError

    def find_by_id(self, enrollment_request_id: str) -> EnrollmentRequest | None:
        raise NotImplementedError

    def find_pending_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> EnrollmentRequest | None:
        raise NotImplementedError

    def list_by_company(
        self,
        *,
        company_id: str,
        status: str | None = None,
    ) -> list[EnrollmentRequest]:
        raise NotImplementedError


class CompanyDeviceLinkRepository(Protocol):
    def save(self, link: CompanyDeviceLink) -> CompanyDeviceLink:
        raise NotImplementedError

    def find_by_id(self, company_device_link_id: str) -> CompanyDeviceLink | None:
        raise NotImplementedError

    def find_active_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> CompanyDeviceLink | None:
        raise NotImplementedError

    def list_by_company(self, company_id: str) -> list[CompanyDeviceLink]:
        raise NotImplementedError

    def list_by_device(self, device_id: str) -> list[CompanyDeviceLink]:
        raise NotImplementedError

    def list_active(self) -> list[CompanyDeviceLink]:
        raise NotImplementedError


class AuditorAccessRequestRepository(Protocol):
    def save(self, access_request: AuditorAccessRequest) -> AuditorAccessRequest:
        raise NotImplementedError

    def find_by_id(self, auditor_access_request_id: str) -> AuditorAccessRequest | None:
        raise NotImplementedError


class AuditorSessionRepository(Protocol):
    def save(self, session: AuditorSession) -> AuditorSession:
        raise NotImplementedError

    def find_by_id(self, auditor_session_id: str) -> AuditorSession | None:
        raise NotImplementedError

    def list_active_by_company(self, company_id: str) -> list[AuditorSession]:
        raise NotImplementedError


class AuditorOtpEventRepository(Protocol):
    def save(self, otp_event: AuditorOtpEvent) -> AuditorOtpEvent:
        raise NotImplementedError

    def count_recent_events(
        self,
        *,
        event_type: AuditorOtpEventType,
        since: datetime,
        company_id: str | None = None,
        device_id: str | None = None,
        client_ip: str | None = None,
    ) -> int:
        raise NotImplementedError
