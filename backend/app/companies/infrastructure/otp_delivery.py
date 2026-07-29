from base64 import b64encode
from collections.abc import Callable
from types import TracebackType
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.companies.application.otp_delivery import (
    AuditorOtpDeliveryRequest,
    LocalOtpDeliveryProvider,
    OtpDeliveryError,
    OtpDeliveryProvider,
    OtpDeliveryResult,
)
from backend.app.shared.config import Settings


class HttpResponse(Protocol):
    def __enter__(self) -> "HttpResponse":
        raise NotImplementedError

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        raise NotImplementedError

    def read(self) -> bytes:
        raise NotImplementedError


HttpOpener = Callable[[Request, float], HttpResponse]


class TwilioOtpDeliveryProvider:
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        from_phone_number: str,
        timeout_seconds: float = 10,
        opener: HttpOpener | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_phone_number = from_phone_number
        self._timeout_seconds = timeout_seconds
        self._opener = opener or _default_http_opener

    def deliver_auditor_otp(
        self,
        request: AuditorOtpDeliveryRequest,
    ) -> OtpDeliveryResult:
        body = urlencode(
            {
                "To": request.phone_number,
                "From": self._from_phone_number,
                "Body": _build_auditor_otp_message(request),
            },
        ).encode()
        http_request = Request(
            url=(
                "https://api.twilio.com/2010-04-01/Accounts/"
                f"{self._account_sid}/Messages.json"
            ),
            data=body,
            headers={
                "Authorization": _basic_auth_header(self._account_sid, self._auth_token),
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "the-all-seeing-eye-backend/otp",
            },
            method="POST",
        )

        try:
            with self._opener(http_request, self._timeout_seconds) as response:
                response.read()
        except HTTPError as exc:
            error_body = exc.read().decode(errors="replace")
            raise OtpDeliveryError(
                f"Twilio respondio {exc.code} al enviar OTP: {error_body}",
            ) from exc
        except URLError as exc:
            raise OtpDeliveryError(f"No se pudo conectar con Twilio: {exc.reason}") from exc

        return OtpDeliveryResult(delivery_channel="sms")


def build_otp_delivery_provider(settings: Settings) -> OtpDeliveryProvider:
    provider = settings.otp_delivery_provider.lower()
    if provider == "local":
        return LocalOtpDeliveryProvider(
            expose_verification_code=settings.app_env.lower() in {"local", "test", "development"},
        )
    if provider == "twilio":
        return TwilioOtpDeliveryProvider(
            account_sid=settings.twilio_account_sid or "",
            auth_token=settings.twilio_auth_token or "",
            from_phone_number=settings.twilio_from_phone_number or "",
            timeout_seconds=settings.otp_delivery_timeout_seconds,
        )
    raise OtpDeliveryError(f"Proveedor OTP no soportado: {settings.otp_delivery_provider}")


def _build_auditor_otp_message(request: AuditorOtpDeliveryRequest) -> str:
    return (
        f"Codigo auditor The All Seeing Eye para {request.company_name}: "
        f"{request.verification_code}. Expira en 10 minutos. "
        f"Dispositivo solicitante: {request.device_id}."
    )


def _basic_auth_header(username: str, password: str) -> str:
    encoded_credentials = b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded_credentials}"


def _default_http_opener(request: Request, timeout_seconds: float) -> HttpResponse:
    return cast(HttpResponse, urlopen(request, timeout=timeout_seconds))
