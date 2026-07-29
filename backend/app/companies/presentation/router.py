from ipaddress import ip_address, ip_network
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse

from backend.app.companies.application.create_company import CreateCompanyUseCase
from backend.app.companies.application.create_enrollment_code import (
    CreateEnrollmentCodeUseCase,
)
from backend.app.companies.application.query_company_summary import (
    QueryCompanySummaryCommand,
    QueryCompanySummaryUseCase,
)
from backend.app.companies.application.query_device_company_links import (
    QueryDeviceCompanyLinksCommand,
    QueryDeviceCompanyLinksUseCase,
)
from backend.app.companies.application.request_auditor_access import (
    OtpRateLimitExceeded,
    OtpRateLimitPolicy,
    RequestAuditorAccessUseCase,
)
from backend.app.companies.application.request_device_enrollment import (
    RequestDeviceEnrollmentUseCase,
)
from backend.app.companies.application.review_enrollment_request import (
    ReviewEnrollmentRequestUseCase,
)
from backend.app.companies.application.revoke_device_company_link import (
    RevokeDeviceCompanyLinkUseCase,
)
from backend.app.companies.application.verify_auditor_access import (
    VerifyAuditorAccessUseCase,
)
from backend.app.companies.presentation.schemas import (
    AuditorAccessRequestResponse,
    AuditorSessionResponse,
    CompanyResponse,
    CompanySummaryResponse,
    CreateCompanyRequest,
    CreateEnrollmentCodeRequest,
    DeviceCompanyLinkResponse,
    EnrollmentCodeResponse,
    EnrollmentRequestResponse,
    RequestAuditorAccessRequest,
    RequestDeviceEnrollmentRequest,
    ReviewedEnrollmentRequestResponse,
    ReviewEnrollmentRequestRequest,
    RevokeDeviceCompanyLinkRequest,
    VerifyAuditorAccessRequest,
)
from backend.app.shared.container import AppContainer
from backend.app.shared.dependencies import get_container
from backend.app.shared.security import require_agent_token, require_auditor_session

router = APIRouter(prefix="/companies", tags=["companies"])

_CLIENT_IP_HEADERS = (
    "X-Forwarded-For",
    "X-Real-IP",
    "CF-Connecting-IP",
)


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    settings = request.app.state.container.settings
    if _is_trusted_proxy(request.client.host, settings.trusted_proxy_ips):
        for header_name in _CLIENT_IP_HEADERS:
            forwarded_ip = _first_valid_ip(request.headers.get(header_name))
            if forwarded_ip is not None:
                return forwarded_ip
    return request.client.host


def _first_valid_ip(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None

    for candidate in raw_value.split(","):
        try:
            return str(ip_address(candidate.strip()))
        except ValueError:
            continue
    return None


def _is_trusted_proxy(client_host: str, trusted_proxy_ips: str) -> bool:
    trusted_ranges = [
        raw_range.strip()
        for raw_range in trusted_proxy_ips.split(",")
        if raw_range.strip()
    ]
    if not trusted_ranges:
        return False

    try:
        client_ip = ip_address(client_host)
    except ValueError:
        return False

    for raw_range in trusted_ranges:
        try:
            if client_ip in ip_network(raw_range, strict=False):
                return True
        except ValueError:
            continue
    return False


def _otp_rate_limit_policy(request: Request) -> OtpRateLimitPolicy:
    settings = request.app.state.container.settings
    return OtpRateLimitPolicy(
        window_seconds=settings.otp_rate_limit_window_seconds,
        max_per_company=settings.otp_rate_limit_max_per_company,
        max_per_device=settings.otp_rate_limit_max_per_device,
        max_per_ip=settings.otp_rate_limit_max_per_ip,
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CreateCompanyRequest,
    container: Annotated[AppContainer, Depends(get_container)],
) -> CompanyResponse:
    use_case = CreateCompanyUseCase(container.company_repository)
    company = use_case.execute(payload.to_command())
    return CompanyResponse.from_domain(company)


@router.get("/device-links", response_model=list[DeviceCompanyLinkResponse])
async def list_device_links(
    device_id: Annotated[str, Query(min_length=1)],
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> list[DeviceCompanyLinkResponse]:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=device_id,
        require_registered_device=True,
    )
    use_case = QueryDeviceCompanyLinksUseCase(
        container.company_device_link_repository,
        container.company_repository,
    )
    return [
        DeviceCompanyLinkResponse.from_result(link)
        for link in use_case.execute(QueryDeviceCompanyLinksCommand(device_id=device_id))
    ]


@router.post(
    "/device-links/{company_device_link_id}/revoke",
    response_model=DeviceCompanyLinkResponse,
)
async def revoke_device_link(
    company_device_link_id: str,
    payload: RevokeDeviceCompanyLinkRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> DeviceCompanyLinkResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    use_case = RevokeDeviceCompanyLinkUseCase(container.company_device_link_repository)
    link = use_case.execute(payload.to_command(company_device_link_id))
    company = container.company_repository.find_by_id(link.company_id)
    return DeviceCompanyLinkResponse.from_domain(
        link,
        company_name=company.name if company is not None else link.company_id,
    )


@router.post(
    "/{company_id}/auditor-access-requests",
    response_model=AuditorAccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_auditor_access(
    company_id: str,
    payload: RequestAuditorAccessRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> AuditorAccessRequestResponse | JSONResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    use_case = RequestAuditorAccessUseCase(
        container.company_repository,
        container.auditor_access_request_repository,
        otp_delivery_provider=container.otp_delivery_provider,
        otp_event_repository=container.auditor_otp_event_repository,
        otp_rate_limit_policy=_otp_rate_limit_policy(request),
    )
    try:
        result = use_case.execute(
            payload.to_command(company_id, client_ip=_client_ip(request)),
        )
    except OtpRateLimitExceeded as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": str(exc)},
        )
    return AuditorAccessRequestResponse.from_result(
        result,
    )


@router.post(
    "/{company_id}/auditor-access-requests/{auditor_access_request_id}/verify",
    response_model=AuditorSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def verify_auditor_access(
    company_id: str,
    auditor_access_request_id: str,
    payload: VerifyAuditorAccessRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> AuditorSessionResponse | JSONResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    use_case = VerifyAuditorAccessUseCase(
        container.auditor_access_request_repository,
        container.auditor_session_repository,
        otp_event_repository=container.auditor_otp_event_repository,
    )
    result = use_case.execute(
        payload.to_command(
            company_id=company_id,
            auditor_access_request_id=auditor_access_request_id,
            client_ip=_client_ip(request),
        ),
    )
    if not result.is_success or result.session is None:
        return JSONResponse(
            status_code=422,
            content={"detail": result.error_detail or "Solicitud de auditor invalida"},
        )
    return AuditorSessionResponse.from_domain(result.session)


@router.post(
    "/{company_id}/enrollment-codes",
    response_model=EnrollmentCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_enrollment_code(
    company_id: str,
    payload: CreateEnrollmentCodeRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> EnrollmentCodeResponse:
    require_auditor_session(
        request,
        request.app.state.container.settings,
        container,
        company_id=company_id,
        required_scope="devices:approve",
    )
    use_case = CreateEnrollmentCodeUseCase(
        container.company_repository,
        container.enrollment_code_repository,
    )
    result = use_case.execute(payload.to_command(company_id))
    return EnrollmentCodeResponse.from_result(result)


@router.post(
    "/enrollment-requests",
    response_model=EnrollmentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_device_enrollment(
    payload: RequestDeviceEnrollmentRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> EnrollmentRequestResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    use_case = RequestDeviceEnrollmentUseCase(
        container.enrollment_code_repository,
        container.enrollment_request_repository,
        container.company_device_link_repository,
    )
    enrollment_request = use_case.execute(payload.to_command())
    return EnrollmentRequestResponse.from_domain(enrollment_request)


@router.get(
    "/{company_id}/enrollment-requests",
    response_model=list[EnrollmentRequestResponse],
)
async def list_enrollment_requests(
    company_id: str,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[EnrollmentRequestResponse]:
    require_auditor_session(
        request,
        request.app.state.container.settings,
        container,
        company_id=company_id,
        required_scope="devices:read",
    )
    enrollment_requests = container.enrollment_request_repository.list_by_company(
        company_id=company_id,
        status=status_filter,
    )
    return [
        EnrollmentRequestResponse.from_domain(enrollment_request)
        for enrollment_request in enrollment_requests
    ]


@router.post(
    "/{company_id}/enrollment-requests/{enrollment_request_id}/review",
    response_model=ReviewedEnrollmentRequestResponse,
)
async def review_enrollment_request(
    company_id: str,
    enrollment_request_id: str,
    payload: ReviewEnrollmentRequestRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> ReviewedEnrollmentRequestResponse:
    auditor_session = require_auditor_session(
        request,
        request.app.state.container.settings,
        container,
        company_id=company_id,
        required_scope="devices:approve",
    )
    use_case = ReviewEnrollmentRequestUseCase(
        container.enrollment_request_repository,
        container.company_device_link_repository,
    )
    result = use_case.execute(
        payload.to_command(
            company_id=company_id,
            enrollment_request_id=enrollment_request_id,
            auditor_session_id=auditor_session.auditor_session_id,
        ),
    )
    return ReviewedEnrollmentRequestResponse.from_result(result)


@router.get("/{company_id}/summary", response_model=CompanySummaryResponse)
async def get_company_summary(
    company_id: str,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> CompanySummaryResponse:
    require_auditor_session(
        request,
        request.app.state.container.settings,
        container,
        company_id=company_id,
        required_scope="company:read",
    )
    use_case = QueryCompanySummaryUseCase(
        container.company_repository,
        container.company_device_link_repository,
        container.enrollment_request_repository,
        container.auditor_session_repository,
        container.device_repository,
    )
    summary = use_case.execute(
        QueryCompanySummaryCommand(
            company_id=company_id,
            heartbeat_timeout_seconds=(
                request.app.state.container.settings.agent_heartbeat_timeout_seconds
            ),
        ),
    )
    return CompanySummaryResponse.from_result(summary)
