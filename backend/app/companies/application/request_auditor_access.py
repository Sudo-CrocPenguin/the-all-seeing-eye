from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from backend.app.companies.application.otp_delivery import (
    AuditorOtpDeliveryRequest,
    LocalOtpDeliveryProvider,
    OtpDeliveryProvider,
)
from backend.app.companies.application.secret_hasher import SecretHasher
from backend.app.companies.domain.entities import (
    AuditorAccessRequest,
    AuditorOtpEvent,
    AuditorOtpEventType,
)
from backend.app.companies.domain.repositories import (
    AuditorAccessRequestRepository,
    AuditorOtpEventRepository,
    CompanyRepository,
)
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now


class OtpRateLimitExceeded(DomainValidationError):
    pass


@dataclass(frozen=True, slots=True)
class RequestAuditorAccessCommand:
    company_id: str
    device_id: str
    client_ip: str | None = None
    otp_ttl_seconds: int = 600


@dataclass(frozen=True, slots=True)
class OtpRateLimitPolicy:
    window_seconds: int = 600
    max_per_company: int = 5
    max_per_device: int = 3
    max_per_ip: int = 20


@dataclass(frozen=True, slots=True)
class RequestedAuditorAccess:
    access_request: AuditorAccessRequest
    delivery_channel: str
    verification_code: str | None


class RequestAuditorAccessUseCase:
    def __init__(
        self,
        company_repository: CompanyRepository,
        access_request_repository: AuditorAccessRequestRepository,
        secret_hasher: SecretHasher | None = None,
        otp_delivery_provider: OtpDeliveryProvider | None = None,
        otp_event_repository: AuditorOtpEventRepository | None = None,
        otp_rate_limit_policy: OtpRateLimitPolicy | None = None,
    ) -> None:
        self._company_repository = company_repository
        self._access_request_repository = access_request_repository
        self._secret_hasher = secret_hasher or SecretHasher()
        self._otp_delivery_provider = otp_delivery_provider
        self._otp_event_repository = otp_event_repository
        self._otp_rate_limit_policy = otp_rate_limit_policy or OtpRateLimitPolicy()

    def execute(
        self,
        command: RequestAuditorAccessCommand,
        *,
        expose_verification_code: bool = False,
    ) -> RequestedAuditorAccess:
        company = self._company_repository.find_by_id(command.company_id)
        if company is None or not company.is_active:
            raise DomainValidationError("Empresa no encontrada o inactiva")

        requested_at = utc_now()
        self._enforce_rate_limit(command, requested_at)

        verification_code = self._secret_hasher.generate_numeric_code()
        hashed_code = self._secret_hasher.hash_secret(verification_code)
        access_request = AuditorAccessRequest(
            auditor_access_request_id=str(uuid4()),
            company_id=command.company_id,
            device_id=command.device_id,
            otp_hash=hashed_code.secret_hash,
            otp_salt=hashed_code.secret_salt,
            requested_at=requested_at,
            expires_at=requested_at + timedelta(seconds=max(command.otp_ttl_seconds, 60)),
        )
        saved_request = self._access_request_repository.save(access_request)
        otp_delivery_provider = self._otp_delivery_provider or LocalOtpDeliveryProvider(
            expose_verification_code=expose_verification_code,
        )
        delivery_result = otp_delivery_provider.deliver_auditor_otp(
            AuditorOtpDeliveryRequest(
                company_id=company.company_id,
                company_name=company.name,
                phone_number=company.phone_number,
                device_id=command.device_id,
                verification_code=verification_code,
                expires_at=access_request.expires_at,
            ),
        )
        self._record_otp_event(
            event_type=AuditorOtpEventType.REQUESTED,
            command=command,
            occurred_at=requested_at,
            auditor_access_request_id=saved_request.auditor_access_request_id,
        )
        return RequestedAuditorAccess(
            access_request=saved_request,
            delivery_channel=delivery_result.delivery_channel,
            verification_code=delivery_result.exposed_verification_code,
        )

    def _enforce_rate_limit(
        self,
        command: RequestAuditorAccessCommand,
        requested_at: datetime,
    ) -> None:
        if self._otp_event_repository is None:
            return

        since = requested_at - timedelta(
            seconds=max(self._otp_rate_limit_policy.window_seconds, 1),
        )
        exceeded_reason = self._first_exceeded_rate_limit(command, since)
        if exceeded_reason is None:
            return

        self._record_otp_event(
            event_type=AuditorOtpEventType.BLOCKED,
            command=command,
            occurred_at=requested_at,
            event_metadata={"reason": exceeded_reason},
        )
        raise OtpRateLimitExceeded(f"Limite de solicitudes OTP excedido: {exceeded_reason}")

    def _first_exceeded_rate_limit(
        self,
        command: RequestAuditorAccessCommand,
        since: datetime,
    ) -> str | None:
        if self._otp_event_repository is None:
            return None

        company_count = self._otp_event_repository.count_recent_events(
            event_type=AuditorOtpEventType.REQUESTED,
            since=since,
            company_id=command.company_id,
        )
        if company_count >= max(self._otp_rate_limit_policy.max_per_company, 1):
            return "empresa"

        device_count = self._otp_event_repository.count_recent_events(
            event_type=AuditorOtpEventType.REQUESTED,
            since=since,
            device_id=command.device_id,
        )
        if device_count >= max(self._otp_rate_limit_policy.max_per_device, 1):
            return "dispositivo"

        if command.client_ip:
            ip_count = self._otp_event_repository.count_recent_events(
                event_type=AuditorOtpEventType.REQUESTED,
                since=since,
                client_ip=command.client_ip,
            )
            if ip_count >= max(self._otp_rate_limit_policy.max_per_ip, 1):
                return "ip"
        return None

    def _record_otp_event(
        self,
        *,
        event_type: AuditorOtpEventType,
        command: RequestAuditorAccessCommand,
        occurred_at: datetime,
        auditor_access_request_id: str | None = None,
        event_metadata: dict[str, str] | None = None,
    ) -> None:
        if self._otp_event_repository is None:
            return
        self._otp_event_repository.save(
            AuditorOtpEvent(
                otp_event_id=str(uuid4()),
                company_id=command.company_id,
                device_id=command.device_id,
                client_ip=command.client_ip,
                auditor_access_request_id=auditor_access_request_id,
                event_type=event_type,
                occurred_at=occurred_at,
                event_metadata=event_metadata or {},
            ),
        )
