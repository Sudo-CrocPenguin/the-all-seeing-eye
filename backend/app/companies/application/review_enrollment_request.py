from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from backend.app.companies.domain.entities import CompanyDeviceLink
from backend.app.companies.domain.repositories import (
    CompanyDeviceLinkRepository,
    EnrollmentRequestRepository,
)
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now

EnrollmentReviewDecision = Literal["ACCEPT", "DENY"]


@dataclass(frozen=True, slots=True)
class ReviewEnrollmentRequestCommand:
    company_id: str
    enrollment_request_id: str
    auditor_session_id: str
    decision: EnrollmentReviewDecision


@dataclass(frozen=True, slots=True)
class ReviewedEnrollmentRequest:
    enrollment_request_id: str
    company_id: str
    device_id: str
    status: str
    link: CompanyDeviceLink | None = None


class ReviewEnrollmentRequestUseCase:
    def __init__(
        self,
        enrollment_request_repository: EnrollmentRequestRepository,
        company_device_link_repository: CompanyDeviceLinkRepository,
    ) -> None:
        self._enrollment_request_repository = enrollment_request_repository
        self._company_device_link_repository = company_device_link_repository

    def execute(self, command: ReviewEnrollmentRequestCommand) -> ReviewedEnrollmentRequest:
        enrollment_request = self._enrollment_request_repository.find_by_id(
            command.enrollment_request_id,
        )
        if enrollment_request is None:
            raise DomainValidationError("Solicitud de vinculacion no encontrada")
        if enrollment_request.company_id != command.company_id:
            raise DomainValidationError("La solicitud no pertenece a esta empresa")

        reviewed_at = utc_now()
        link = None
        if command.decision == "ACCEPT":
            enrollment_request.accept(command.auditor_session_id, reviewed_at)
            link = self._ensure_link(enrollment_request.company_id, enrollment_request.device_id)
        elif command.decision == "DENY":
            enrollment_request.deny(command.auditor_session_id, reviewed_at)
        else:
            raise DomainValidationError("decision debe ser ACCEPT o DENY")

        saved_request = self._enrollment_request_repository.save(enrollment_request)
        return ReviewedEnrollmentRequest(
            enrollment_request_id=saved_request.enrollment_request_id,
            company_id=saved_request.company_id,
            device_id=saved_request.device_id,
            status=saved_request.status.value,
            link=link,
        )

    def _ensure_link(self, company_id: str, device_id: str) -> CompanyDeviceLink:
        existing_link = self._company_device_link_repository.find_active_by_company_and_device(
            company_id=company_id,
            device_id=device_id,
        )
        if existing_link is not None:
            return existing_link

        link = CompanyDeviceLink(
            company_device_link_id=str(uuid4()),
            company_id=company_id,
            device_id=device_id,
            linked_at=utc_now(),
        )
        return self._company_device_link_repository.save(link)
