from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from backend.app.companies.application.otp_delivery import (
    AuditorOtpDeliveryRequest,
    LocalOtpDeliveryProvider,
    OtpDeliveryProvider,
)
from backend.app.companies.application.secret_hasher import SecretHasher
from backend.app.companies.domain.entities import AuditorAccessRequest
from backend.app.companies.domain.repositories import (
    AuditorAccessRequestRepository,
    CompanyRepository,
)
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class RequestAuditorAccessCommand:
    company_id: str
    device_id: str
    otp_ttl_seconds: int = 600


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
    ) -> None:
        self._company_repository = company_repository
        self._access_request_repository = access_request_repository
        self._secret_hasher = secret_hasher or SecretHasher()
        self._otp_delivery_provider = otp_delivery_provider

    def execute(
        self,
        command: RequestAuditorAccessCommand,
        *,
        expose_verification_code: bool = False,
    ) -> RequestedAuditorAccess:
        company = self._company_repository.find_by_id(command.company_id)
        if company is None or not company.is_active:
            raise DomainValidationError("Empresa no encontrada o inactiva")

        verification_code = self._secret_hasher.generate_numeric_code()
        hashed_code = self._secret_hasher.hash_secret(verification_code)
        requested_at = utc_now()
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
        return RequestedAuditorAccess(
            access_request=saved_request,
            delivery_channel=delivery_result.delivery_channel,
            verification_code=delivery_result.exposed_verification_code,
        )
