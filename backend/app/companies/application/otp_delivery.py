from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class OtpDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AuditorOtpDeliveryRequest:
    company_id: str
    company_name: str
    phone_number: str
    device_id: str
    verification_code: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OtpDeliveryResult:
    delivery_channel: str
    exposed_verification_code: str | None = None


class OtpDeliveryProvider(Protocol):
    def deliver_auditor_otp(
        self,
        request: AuditorOtpDeliveryRequest,
    ) -> OtpDeliveryResult:
        raise NotImplementedError


class LocalOtpDeliveryProvider:
    def __init__(self, *, expose_verification_code: bool) -> None:
        self._expose_verification_code = expose_verification_code

    def deliver_auditor_otp(
        self,
        request: AuditorOtpDeliveryRequest,
    ) -> OtpDeliveryResult:
        return OtpDeliveryResult(
            delivery_channel="local_response",
            exposed_verification_code=(
                request.verification_code if self._expose_verification_code else None
            ),
        )
