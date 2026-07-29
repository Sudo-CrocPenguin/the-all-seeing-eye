from datetime import datetime
from threading import Lock

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


class InMemoryCompanyRepository:
    def __init__(self) -> None:
        self._items: dict[str, Company] = {}
        self._lock = Lock()

    def save(self, company: Company) -> Company:
        with self._lock:
            self._items[company.company_id] = company
        return company

    def find_by_id(self, company_id: str) -> Company | None:
        with self._lock:
            return self._items.get(company_id)

    def list_all(self) -> list[Company]:
        with self._lock:
            return list(self._items.values())


class InMemoryEnrollmentCodeRepository:
    def __init__(self) -> None:
        self._items: dict[str, EnrollmentCode] = {}
        self._lock = Lock()

    def save(self, enrollment_code: EnrollmentCode) -> EnrollmentCode:
        with self._lock:
            self._items[enrollment_code.enrollment_code_id] = enrollment_code
        return enrollment_code

    def find_by_id(self, enrollment_code_id: str) -> EnrollmentCode | None:
        with self._lock:
            return self._items.get(enrollment_code_id)

    def find_by_code_digest(self, code_digest: str) -> EnrollmentCode | None:
        with self._lock:
            for item in self._items.values():
                if item.code_digest == code_digest:
                    return item
        return None


class InMemoryEnrollmentRequestRepository:
    def __init__(self) -> None:
        self._items: dict[str, EnrollmentRequest] = {}
        self._lock = Lock()

    def save(self, enrollment_request: EnrollmentRequest) -> EnrollmentRequest:
        with self._lock:
            self._items[enrollment_request.enrollment_request_id] = enrollment_request
        return enrollment_request

    def find_by_id(self, enrollment_request_id: str) -> EnrollmentRequest | None:
        with self._lock:
            return self._items.get(enrollment_request_id)

    def find_pending_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> EnrollmentRequest | None:
        with self._lock:
            for item in self._items.values():
                if (
                    item.company_id == company_id
                    and item.device_id == device_id
                    and item.is_pending
                ):
                    return item
        return None

    def list_by_company(
        self,
        *,
        company_id: str,
        status: str | None = None,
    ) -> list[EnrollmentRequest]:
        with self._lock:
            items = [item for item in self._items.values() if item.company_id == company_id]
        if status:
            items = [item for item in items if item.status.value == status]
        items.sort(key=lambda item: item.requested_at, reverse=True)
        return items


class InMemoryCompanyDeviceLinkRepository:
    def __init__(self) -> None:
        self._items: dict[str, CompanyDeviceLink] = {}
        self._lock = Lock()

    def save(self, link: CompanyDeviceLink) -> CompanyDeviceLink:
        with self._lock:
            self._items[link.company_device_link_id] = link
        return link

    def find_by_id(self, company_device_link_id: str) -> CompanyDeviceLink | None:
        with self._lock:
            return self._items.get(company_device_link_id)

    def find_active_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> CompanyDeviceLink | None:
        with self._lock:
            for item in self._items.values():
                if (
                    item.company_id == company_id
                    and item.device_id == device_id
                    and item.is_active
                ):
                    return item
        return None

    def list_by_company(self, company_id: str) -> list[CompanyDeviceLink]:
        with self._lock:
            return [item for item in self._items.values() if item.company_id == company_id]

    def list_by_device(self, device_id: str) -> list[CompanyDeviceLink]:
        with self._lock:
            return [item for item in self._items.values() if item.device_id == device_id]

    def list_active(self) -> list[CompanyDeviceLink]:
        with self._lock:
            return [item for item in self._items.values() if item.is_active]


class InMemoryAuditorAccessRequestRepository:
    def __init__(self) -> None:
        self._items: dict[str, AuditorAccessRequest] = {}
        self._lock = Lock()

    def save(self, access_request: AuditorAccessRequest) -> AuditorAccessRequest:
        with self._lock:
            self._items[access_request.auditor_access_request_id] = access_request
        return access_request

    def find_by_id(self, auditor_access_request_id: str) -> AuditorAccessRequest | None:
        with self._lock:
            return self._items.get(auditor_access_request_id)


class InMemoryAuditorSessionRepository:
    def __init__(self) -> None:
        self._items: dict[str, AuditorSession] = {}
        self._lock = Lock()

    def save(self, session: AuditorSession) -> AuditorSession:
        with self._lock:
            self._items[session.auditor_session_id] = session
        return session

    def find_by_id(self, auditor_session_id: str) -> AuditorSession | None:
        with self._lock:
            return self._items.get(auditor_session_id)

    def list_active_by_company(self, company_id: str) -> list[AuditorSession]:
        with self._lock:
            return [
                item
                for item in self._items.values()
                if item.company_id == company_id and item.is_active()
            ]


class InMemoryAuditorOtpEventRepository:
    def __init__(self) -> None:
        self._items: dict[str, AuditorOtpEvent] = {}
        self._lock = Lock()

    def save(self, otp_event: AuditorOtpEvent) -> AuditorOtpEvent:
        with self._lock:
            self._items[otp_event.otp_event_id] = otp_event
        return otp_event

    def count_recent_events(
        self,
        *,
        event_type: AuditorOtpEventType,
        since: datetime,
        company_id: str | None = None,
        device_id: str | None = None,
        client_ip: str | None = None,
    ) -> int:
        with self._lock:
            events = [
                item
                for item in self._items.values()
                if item.event_type == event_type and item.occurred_at >= since
            ]
        if company_id is not None:
            events = [item for item in events if item.company_id == company_id]
        if device_id is not None:
            events = [item for item in events if item.device_id == device_id]
        if client_ip is not None:
            events = [item for item in events if item.client_ip == client_ip]
        return len(events)
