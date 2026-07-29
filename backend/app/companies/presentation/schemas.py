from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.companies.application.create_company import CreateCompanyCommand
from backend.app.companies.application.create_enrollment_code import (
    CreatedEnrollmentCode,
    CreateEnrollmentCodeCommand,
)
from backend.app.companies.application.query_company_summary import CompanySummary
from backend.app.companies.application.query_device_company_links import DeviceCompanyLink
from backend.app.companies.application.request_auditor_access import (
    RequestAuditorAccessCommand,
    RequestedAuditorAccess,
)
from backend.app.companies.application.request_device_enrollment import (
    RequestDeviceEnrollmentCommand,
)
from backend.app.companies.application.review_enrollment_request import (
    ReviewedEnrollmentRequest,
    ReviewEnrollmentRequestCommand,
)
from backend.app.companies.application.revoke_device_company_link import (
    RevokeDeviceCompanyLinkCommand,
)
from backend.app.companies.application.verify_auditor_access import VerifyAuditorAccessCommand
from backend.app.companies.domain.entities import (
    AuditorSession,
    Company,
    CompanyDeviceLink,
    EnrollmentRequest,
)


class CreateCompanyRequest(BaseModel):
    name: str
    phone_number: str

    def to_command(self) -> CreateCompanyCommand:
        return CreateCompanyCommand(name=self.name, phone_number=self.phone_number)


class CompanyResponse(BaseModel):
    company_id: str
    name: str
    phone_number: str
    created_at: datetime
    status: str

    @classmethod
    def from_domain(cls, company: Company) -> "CompanyResponse":
        return cls(
            company_id=company.company_id,
            name=company.name,
            phone_number=company.phone_number,
            created_at=company.created_at,
            status=company.status.value,
        )


class RequestAuditorAccessRequest(BaseModel):
    device_id: str

    def to_command(self, company_id: str) -> RequestAuditorAccessCommand:
        return RequestAuditorAccessCommand(company_id=company_id, device_id=self.device_id)


class AuditorAccessRequestResponse(BaseModel):
    auditor_access_request_id: str
    company_id: str
    device_id: str
    requested_at: datetime
    expires_at: datetime
    status: str
    delivery_channel: str
    verification_code: str | None = None

    @classmethod
    def from_result(
        cls,
        result: RequestedAuditorAccess,
        *,
        delivery_channel: str,
    ) -> "AuditorAccessRequestResponse":
        access_request = result.access_request
        return cls(
            auditor_access_request_id=access_request.auditor_access_request_id,
            company_id=access_request.company_id,
            device_id=access_request.device_id,
            requested_at=access_request.requested_at,
            expires_at=access_request.expires_at,
            status=access_request.status.value,
            delivery_channel=delivery_channel,
            verification_code=result.verification_code,
        )


class VerifyAuditorAccessRequest(BaseModel):
    device_id: str
    verification_code: str

    def to_command(
        self,
        *,
        company_id: str,
        auditor_access_request_id: str,
    ) -> VerifyAuditorAccessCommand:
        return VerifyAuditorAccessCommand(
            auditor_access_request_id=auditor_access_request_id,
            company_id=company_id,
            device_id=self.device_id,
            verification_code=self.verification_code,
        )


class AuditorSessionResponse(BaseModel):
    auditor_session_id: str
    company_id: str
    device_id: str
    created_at: datetime
    expires_at: datetime
    scopes: list[str]
    revoked_at: datetime | None

    @classmethod
    def from_domain(cls, session: AuditorSession) -> "AuditorSessionResponse":
        return cls(
            auditor_session_id=session.auditor_session_id,
            company_id=session.company_id,
            device_id=session.device_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            scopes=list(session.scopes),
            revoked_at=session.revoked_at,
        )


class CreateEnrollmentCodeRequest(BaseModel):
    ttl_seconds: int = Field(default=86_400, ge=60, le=604_800)
    max_uses: int = Field(default=1, ge=1, le=100)

    def to_command(self, company_id: str) -> CreateEnrollmentCodeCommand:
        return CreateEnrollmentCodeCommand(
            company_id=company_id,
            ttl_seconds=self.ttl_seconds,
            max_uses=self.max_uses,
        )


class EnrollmentCodeResponse(BaseModel):
    enrollment_code_id: str
    company_id: str
    code: str
    created_at: datetime
    expires_at: datetime
    max_uses: int
    used_count: int

    @classmethod
    def from_result(cls, result: CreatedEnrollmentCode) -> "EnrollmentCodeResponse":
        enrollment_code = result.enrollment_code
        return cls(
            enrollment_code_id=enrollment_code.enrollment_code_id,
            company_id=enrollment_code.company_id,
            code=result.code,
            created_at=enrollment_code.created_at,
            expires_at=enrollment_code.expires_at,
            max_uses=enrollment_code.max_uses,
            used_count=enrollment_code.used_count,
        )


class RequestDeviceEnrollmentRequest(BaseModel):
    device_id: str
    enrollment_code: str
    device_fingerprint_snapshot: dict[str, str] = Field(default_factory=dict)

    def to_command(self) -> RequestDeviceEnrollmentCommand:
        return RequestDeviceEnrollmentCommand(
            device_id=self.device_id,
            enrollment_code=self.enrollment_code,
            device_fingerprint_snapshot=self.device_fingerprint_snapshot,
        )


class EnrollmentRequestResponse(BaseModel):
    enrollment_request_id: str
    company_id: str
    device_id: str
    requested_at: datetime
    status: str
    reviewed_by_auditor_session_id: str | None
    reviewed_at: datetime | None
    device_fingerprint_snapshot: dict[str, str]

    @classmethod
    def from_domain(cls, enrollment_request: EnrollmentRequest) -> "EnrollmentRequestResponse":
        return cls(
            enrollment_request_id=enrollment_request.enrollment_request_id,
            company_id=enrollment_request.company_id,
            device_id=enrollment_request.device_id,
            requested_at=enrollment_request.requested_at,
            status=enrollment_request.status.value,
            reviewed_by_auditor_session_id=(
                enrollment_request.reviewed_by_auditor_session_id
            ),
            reviewed_at=enrollment_request.reviewed_at,
            device_fingerprint_snapshot=dict(enrollment_request.device_fingerprint_snapshot),
        )


class ReviewEnrollmentRequestRequest(BaseModel):
    decision: Literal["ACCEPT", "DENY"]

    def to_command(
        self,
        *,
        company_id: str,
        enrollment_request_id: str,
        auditor_session_id: str,
    ) -> ReviewEnrollmentRequestCommand:
        return ReviewEnrollmentRequestCommand(
            company_id=company_id,
            enrollment_request_id=enrollment_request_id,
            auditor_session_id=auditor_session_id,
            decision=self.decision,
        )


class CompanyDeviceLinkResponse(BaseModel):
    company_device_link_id: str
    company_id: str
    device_id: str
    linked_at: datetime
    status: str
    revoked_at: datetime | None
    revoked_by_device: bool
    revoked_by_auditor_session_id: str | None

    @classmethod
    def from_domain(cls, link: CompanyDeviceLink) -> "CompanyDeviceLinkResponse":
        return cls(
            company_device_link_id=link.company_device_link_id,
            company_id=link.company_id,
            device_id=link.device_id,
            linked_at=link.linked_at,
            status=link.status.value,
            revoked_at=link.revoked_at,
            revoked_by_device=link.revoked_by_device,
            revoked_by_auditor_session_id=link.revoked_by_auditor_session_id,
        )


class DeviceCompanyLinkResponse(BaseModel):
    company_device_link_id: str
    company_id: str
    company_name: str
    device_id: str
    linked_at: datetime
    status: str
    revoked_at: datetime | None
    revoked_by_device: bool
    revoked_by_auditor_session_id: str | None

    @classmethod
    def from_result(cls, link: DeviceCompanyLink) -> "DeviceCompanyLinkResponse":
        return cls(
            company_device_link_id=link.company_device_link_id,
            company_id=link.company_id,
            company_name=link.company_name,
            device_id=link.device_id,
            linked_at=link.linked_at,
            status=link.status,
            revoked_at=link.revoked_at,
            revoked_by_device=link.revoked_by_device,
            revoked_by_auditor_session_id=link.revoked_by_auditor_session_id,
        )

    @classmethod
    def from_domain(
        cls,
        link: CompanyDeviceLink,
        *,
        company_name: str,
    ) -> "DeviceCompanyLinkResponse":
        return cls(
            company_device_link_id=link.company_device_link_id,
            company_id=link.company_id,
            company_name=company_name,
            device_id=link.device_id,
            linked_at=link.linked_at,
            status=link.status.value,
            revoked_at=link.revoked_at,
            revoked_by_device=link.revoked_by_device,
            revoked_by_auditor_session_id=link.revoked_by_auditor_session_id,
        )


class RevokeDeviceCompanyLinkRequest(BaseModel):
    device_id: str

    def to_command(self, company_device_link_id: str) -> RevokeDeviceCompanyLinkCommand:
        return RevokeDeviceCompanyLinkCommand(
            device_id=self.device_id,
            company_device_link_id=company_device_link_id,
        )


class ReviewedEnrollmentRequestResponse(BaseModel):
    enrollment_request_id: str
    company_id: str
    device_id: str
    status: str
    link: CompanyDeviceLinkResponse | None

    @classmethod
    def from_result(
        cls,
        result: ReviewedEnrollmentRequest,
    ) -> "ReviewedEnrollmentRequestResponse":
        return cls(
            enrollment_request_id=result.enrollment_request_id,
            company_id=result.company_id,
            device_id=result.device_id,
            status=result.status,
            link=(
                CompanyDeviceLinkResponse.from_domain(result.link)
                if result.link is not None
                else None
            ),
        )


class CompanySummaryResponse(BaseModel):
    company_id: str
    name: str
    status: str
    linked_devices: int
    active_links: int
    connected_devices: int
    without_report_devices: int
    pending_enrollment_requests: int
    active_auditor_sessions: int

    @classmethod
    def from_result(cls, summary: CompanySummary) -> "CompanySummaryResponse":
        return cls(
            company_id=summary.company_id,
            name=summary.name,
            status=summary.status,
            linked_devices=summary.linked_devices,
            active_links=summary.active_links,
            connected_devices=summary.connected_devices,
            without_report_devices=summary.without_report_devices,
            pending_enrollment_requests=summary.pending_enrollment_requests,
            active_auditor_sessions=summary.active_auditor_sessions,
        )
