import argparse
import sys
from pathlib import Path
from typing import Any, Protocol

from auditor.app.config import AuditorSettings
from auditor.app.state import (
    AuditorSessionState,
    AuditorStateError,
    JsonAuditorSessionStore,
    auditor_session_from_response,
)
from auditor.app.transport import (
    AuditorApiClient,
    AuditorTransportError,
    InsecureAuditorBackendUrlError,
)


class AuditorCliApiClient(Protocol):
    def create_company(self, *, name: str, phone_number: str) -> dict[str, Any]:
        raise NotImplementedError

    def request_auditor_access(self, *, company_id: str, device_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def verify_auditor_access(
        self,
        *,
        company_id: str,
        auditor_access_request_id: str,
        device_id: str,
        verification_code: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI de auditoria multiempresa.")
    _add_runtime_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    company_parser = subparsers.add_parser("company", help="Opera empresas auditoras.")
    company_subparsers = company_parser.add_subparsers(dest="company_command", required=True)
    company_create_parser = company_subparsers.add_parser("create", help="Crea una empresa.")
    company_create_parser.add_argument("--name", required=True, help="Nombre de la empresa.")
    company_create_parser.add_argument(
        "--phone",
        required=True,
        help="Telefono receptor de codigos SMS de auditor.",
    )

    access_parser = subparsers.add_parser("access", help="Solicita o verifica acceso auditor.")
    access_subparsers = access_parser.add_subparsers(dest="access_command", required=True)
    access_request_parser = access_subparsers.add_parser(
        "request",
        help="Solicita OTP de auditor para una empresa.",
    )
    access_request_parser.add_argument("--company", required=True, help="company_id.")
    access_request_parser.add_argument("--device-id", help="device_id autorizado.")
    access_verify_parser = access_subparsers.add_parser(
        "verify",
        help="Verifica OTP y guarda sesion temporal.",
    )
    access_verify_parser.add_argument("--company", required=True, help="company_id.")
    access_verify_parser.add_argument("--request", required=True, help="auditor_access_request_id.")
    access_verify_parser.add_argument("--code", required=True, help="Codigo OTP recibido.")
    access_verify_parser.add_argument("--device-id", help="device_id autorizado.")
    return parser


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend-url", help="URL base del backend de auditoria.")
    parser.add_argument("--env-file", help="Archivo KEY=VALUE de configuracion.")
    parser.add_argument("--device-id", help="device_id que solicita acceso auditor.")
    parser.add_argument("--session-file", help="Ruta del JSON de sesion local de auditor.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = _settings_from_args(args)

    try:
        if args.command == "company" and args.company_command == "create":
            _create_company(settings, args.name, args.phone)
            return
        if args.command == "access" and args.access_command == "request":
            _request_access(settings, args.company, args.device_id)
            return
        if args.command == "access" and args.access_command == "verify":
            _verify_access(settings, args.company, args.request, args.code, args.device_id)
            return
        parser.error("Comando no soportado")
    except (AuditorStateError, AuditorTransportError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _settings_from_args(args: argparse.Namespace) -> AuditorSettings:
    settings = AuditorSettings.from_environment(args.env_file)
    return AuditorSettings(
        backend_url=(args.backend_url or settings.backend_url).rstrip("/"),
        device_id=args.device_id or settings.device_id,
        agent_token=settings.agent_token,
        agent_token_header=settings.agent_token_header,
        auditor_session_header=settings.auditor_session_header,
        request_timeout_seconds=settings.request_timeout_seconds,
        session_file=Path(args.session_file) if args.session_file else settings.session_file,
        allow_insecure_transport=settings.allow_insecure_transport,
    )


def _create_company(settings: AuditorSettings, name: str, phone_number: str) -> None:
    response = _build_auditor_api_client(settings).create_company(
        name=name,
        phone_number=phone_number,
    )
    print(f"Empresa creada: {response.get('name', name)} ({response.get('company_id', '')})")


def _request_access(
    settings: AuditorSettings,
    company_id: str,
    device_id: str | None,
) -> None:
    resolved_device_id = _resolve_device_id(settings, device_id)
    response = _build_auditor_api_client(settings).request_auditor_access(
        company_id=company_id,
        device_id=resolved_device_id,
    )
    print(
        "Solicitud de auditor creada: "
        f"{response.get('auditor_access_request_id', '')} "
        f"expires_at={response.get('expires_at', '')} "
        f"delivery={response.get('delivery_channel', '')}",
    )
    verification_code = response.get("verification_code")
    if verification_code:
        print(f"Codigo local: {verification_code}")


def _verify_access(
    settings: AuditorSettings,
    company_id: str,
    auditor_access_request_id: str,
    verification_code: str,
    device_id: str | None,
) -> None:
    resolved_device_id = _resolve_device_id(settings, device_id)
    response = _build_auditor_api_client(settings).verify_auditor_access(
        company_id=company_id,
        auditor_access_request_id=auditor_access_request_id,
        device_id=resolved_device_id,
        verification_code=verification_code,
    )
    session = JsonAuditorSessionStore(settings.session_file).save(
        auditor_session_from_response(response),
    )
    _print_session_saved(session)


def _print_session_saved(session: AuditorSessionState) -> None:
    print(f"Sesion auditor guardada: {session.auditor_session_id}")
    print(f"Company: {session.company_id}")
    print(f"Expires: {session.expires_at}")
    print(f"Scopes: {', '.join(session.scopes)}")


def _resolve_device_id(settings: AuditorSettings, device_id: str | None) -> str:
    resolved_device_id = device_id or settings.device_id
    if not resolved_device_id:
        raise AuditorStateError("AUDITOR_DEVICE_ID o --device-id es obligatorio")
    return resolved_device_id


def _build_auditor_api_client(settings: AuditorSettings) -> AuditorCliApiClient:
    try:
        return AuditorApiClient(
            settings.backend_url,
            agent_token=settings.agent_token,
            agent_token_header=settings.agent_token_header,
            auditor_session_header=settings.auditor_session_header,
            timeout_seconds=settings.request_timeout_seconds,
            allow_insecure_transport=settings.allow_insecure_transport,
        )
    except InsecureAuditorBackendUrlError as exc:
        raise AuditorStateError(str(exc)) from exc


if __name__ == "__main__":
    main()
