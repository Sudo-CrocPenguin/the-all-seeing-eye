import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

from auditor.app.config import AuditorSettings
from auditor.app.export import build_audit_export
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

    def create_enrollment_code(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        ttl_seconds: int,
        max_uses: int,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_enrollment_requests(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def review_enrollment_request(
        self,
        *,
        company_id: str,
        enrollment_request_id: str,
        auditor_session_id: str,
        decision: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def get_company_summary(
        self,
        *,
        company_id: str,
        auditor_session_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def search_network_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def search_lifecycle_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def search_device_movements(
        self,
        *,
        auditor_session_id: str,
        device_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_incident_window(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
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

    enrollment_code_parser = subparsers.add_parser(
        "enrollment-code",
        help="Genera codigos de vinculacion.",
    )
    enrollment_code_subparsers = enrollment_code_parser.add_subparsers(
        dest="enrollment_code_command",
        required=True,
    )
    enrollment_code_create_parser = enrollment_code_subparsers.add_parser(
        "create",
        help="Crea un codigo de vinculacion para agentes.",
    )
    enrollment_code_create_parser.add_argument("--company", help="company_id.")
    enrollment_code_create_parser.add_argument(
        "--ttl-seconds",
        type=int,
        default=86_400,
        help="Vigencia del codigo en segundos.",
    )
    enrollment_code_create_parser.add_argument(
        "--max-uses",
        type=int,
        default=1,
        help="Usos maximos del codigo.",
    )

    enrollment_requests_parser = subparsers.add_parser(
        "enrollment-requests",
        help="Lista o revisa solicitudes de vinculacion.",
    )
    enrollment_requests_subparsers = enrollment_requests_parser.add_subparsers(
        dest="enrollment_requests_command",
        required=True,
    )
    enrollment_requests_list_parser = enrollment_requests_subparsers.add_parser(
        "list",
        help="Lista solicitudes de dispositivos.",
    )
    enrollment_requests_list_parser.add_argument("--company", help="company_id.")
    enrollment_requests_list_parser.add_argument("--status", help="Filtro por estado.")
    enrollment_requests_approve_parser = enrollment_requests_subparsers.add_parser(
        "approve",
        help="Acepta una solicitud de vinculacion.",
    )
    enrollment_requests_approve_parser.add_argument("--company", help="company_id.")
    enrollment_requests_approve_parser.add_argument(
        "--request",
        required=True,
        help="enrollment_request_id.",
    )
    enrollment_requests_deny_parser = enrollment_requests_subparsers.add_parser(
        "deny",
        help="Deniega una solicitud de vinculacion.",
    )
    enrollment_requests_deny_parser.add_argument("--company", help="company_id.")
    enrollment_requests_deny_parser.add_argument(
        "--request",
        required=True,
        help="enrollment_request_id.",
    )

    summary_parser = subparsers.add_parser("summary", help="Muestra resumen de empresa.")
    summary_parser.add_argument("--company", help="company_id.")

    history_parser = subparsers.add_parser("history", help="Consulta historial de auditoria.")
    history_subparsers = history_parser.add_subparsers(dest="history_command", required=True)

    network_history_parser = history_subparsers.add_parser(
        "network",
        help="Consulta eventos de red.",
    )
    _add_company_option(network_history_parser)
    _add_range_options(network_history_parser)
    _add_limit_option(network_history_parser, default=100)
    network_history_parser.add_argument("--device-id", help="Filtro por dispositivo.")
    network_history_parser.add_argument("--local-ip", help="Filtro por IP local.")
    network_history_parser.add_argument("--public-ip", help="Filtro por IP publica.")
    network_history_parser.add_argument("--destination-host", help="Filtro por host destino.")
    network_history_parser.add_argument("--destination-ip", help="Filtro por IP destino.")
    network_history_parser.add_argument("--protocol", help="Filtro por protocolo.")

    lifecycle_history_parser = history_subparsers.add_parser(
        "lifecycle",
        help="Consulta eventos de ciclo de vida.",
    )
    _add_company_option(lifecycle_history_parser)
    _add_range_options(lifecycle_history_parser)
    _add_limit_option(lifecycle_history_parser, default=100)
    lifecycle_history_parser.add_argument("--device-id", help="Filtro por dispositivo.")
    lifecycle_history_parser.add_argument("--event-type", help="Filtro por tipo de evento.")

    movements_history_parser = history_subparsers.add_parser(
        "movements",
        help="Consulta movimientos de un dispositivo.",
    )
    _add_company_option(movements_history_parser)
    _add_range_options(movements_history_parser)
    _add_limit_option(movements_history_parser, default=100)
    movements_history_parser.add_argument("--device-id", required=True, help="device_id.")

    incident_window_parser = history_subparsers.add_parser(
        "incident-window",
        help="Consulta una ventana forense.",
    )
    _add_company_option(incident_window_parser)
    _add_range_options(incident_window_parser)
    incident_window_parser.add_argument("--at", help="Marca central de incidente ISO-8601.")
    incident_window_parser.add_argument(
        "--window-seconds",
        type=int,
        default=900,
        help="Tamano de ventana si se usa --at.",
    )
    _add_limit_option(incident_window_parser, default=500)

    export_parser = subparsers.add_parser(
        "export-json",
        help="Exporta evidencia de auditoria en JSON.",
    )
    _add_company_option(export_parser)
    export_parser.add_argument("--from", dest="from_datetime", required=True, help="Fecha inicial.")
    export_parser.add_argument("--to", dest="to_datetime", required=True, help="Fecha final.")
    export_parser.add_argument("--device-id", help="Filtro opcional por dispositivo.")
    _add_limit_option(export_parser, default=500)
    export_parser.add_argument("--output", help="Archivo destino. Si se omite, imprime stdout.")
    return parser


def _add_company_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--company", help="company_id.")


def _add_range_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="from_datetime", help="Fecha inicial ISO-8601.")
    parser.add_argument("--to", dest="to_datetime", help="Fecha final ISO-8601.")


def _add_limit_option(parser: argparse.ArgumentParser, *, default: int) -> None:
    parser.add_argument("--limit", type=int, default=default, help="Maximo de registros.")


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
        if args.command == "enrollment-code" and args.enrollment_code_command == "create":
            _create_enrollment_code(
                settings,
                args.company,
                args.ttl_seconds,
                args.max_uses,
            )
            return
        if args.command == "enrollment-requests" and args.enrollment_requests_command == "list":
            _list_enrollment_requests(settings, args.company, args.status)
            return
        if args.command == "enrollment-requests" and args.enrollment_requests_command == "approve":
            _review_enrollment_request(settings, args.company, args.request, "ACCEPT")
            return
        if args.command == "enrollment-requests" and args.enrollment_requests_command == "deny":
            _review_enrollment_request(settings, args.company, args.request, "DENY")
            return
        if args.command == "summary":
            _print_summary(settings, args.company)
            return
        if args.command == "history":
            _print_history(settings, args)
            return
        if args.command == "export-json":
            _export_json(settings, args)
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


def _create_enrollment_code(
    settings: AuditorSettings,
    company_id: str | None,
    ttl_seconds: int,
    max_uses: int,
) -> None:
    session = _load_required_session(settings, company_id)
    response = _build_auditor_api_client(settings).create_enrollment_code(
        company_id=session.company_id,
        auditor_session_id=session.auditor_session_id,
        ttl_seconds=ttl_seconds,
        max_uses=max_uses,
    )
    print(f"Codigo de vinculacion: {response.get('code', '')}")
    print(f"Company: {response.get('company_id', session.company_id)}")
    print(f"Expires: {response.get('expires_at', '')}")
    print(f"Max uses: {response.get('max_uses', max_uses)}")


def _list_enrollment_requests(
    settings: AuditorSettings,
    company_id: str | None,
    status_filter: str | None,
) -> None:
    session = _load_required_session(settings, company_id)
    requests = _build_auditor_api_client(settings).list_enrollment_requests(
        company_id=session.company_id,
        auditor_session_id=session.auditor_session_id,
        status_filter=status_filter,
    )
    if not requests:
        print("No hay solicitudes de vinculacion")
        return

    for request in requests:
        print(
            f"{request.get('enrollment_request_id', '')} "
            f"device={request.get('device_id', '')} "
            f"status={request.get('status', '')} "
            f"requested_at={request.get('requested_at', '')}",
        )


def _review_enrollment_request(
    settings: AuditorSettings,
    company_id: str | None,
    enrollment_request_id: str,
    decision: str,
) -> None:
    session = _load_required_session(settings, company_id)
    response = _build_auditor_api_client(settings).review_enrollment_request(
        company_id=session.company_id,
        enrollment_request_id=enrollment_request_id,
        auditor_session_id=session.auditor_session_id,
        decision=decision,
    )
    link = response.get("link")
    if isinstance(link, dict):
        link_label = f" link={link.get('company_device_link_id', '')}"
    else:
        link_label = ""
    print(
        f"Solicitud revisada: {response.get('enrollment_request_id', enrollment_request_id)} "
        f"status={response.get('status', '')}{link_label}",
    )


def _print_summary(settings: AuditorSettings, company_id: str | None) -> None:
    session = _load_required_session(settings, company_id)
    summary = _build_auditor_api_client(settings).get_company_summary(
        company_id=session.company_id,
        auditor_session_id=session.auditor_session_id,
    )
    print(f"Company: {summary.get('name', session.company_id)} ({session.company_id})")
    print(f"Status: {summary.get('status', '')}")
    print(f"Linked devices: {summary.get('linked_devices', 0)}")
    print(f"Active links: {summary.get('active_links', 0)}")
    print(f"Connected devices: {summary.get('connected_devices', 0)}")
    print(f"Without report: {summary.get('without_report_devices', 0)}")
    print(f"Pending enrollment requests: {summary.get('pending_enrollment_requests', 0)}")
    print(f"Active auditor sessions: {summary.get('active_auditor_sessions', 0)}")


def _print_history(settings: AuditorSettings, args: argparse.Namespace) -> None:
    if args.history_command == "network":
        _print_network_history(settings, args)
        return
    if args.history_command == "lifecycle":
        _print_lifecycle_history(settings, args)
        return
    if args.history_command == "movements":
        _print_device_movements_history(settings, args)
        return
    if args.history_command == "incident-window":
        _print_incident_window(settings, args)
        return
    raise AuditorStateError("Comando history no soportado")


def _print_network_history(settings: AuditorSettings, args: argparse.Namespace) -> None:
    session = _load_required_session(settings, args.company)
    events = _build_auditor_api_client(settings).search_network_events(
        auditor_session_id=session.auditor_session_id,
        filters={
            "device_id": args.device_id,
            "local_ip": args.local_ip,
            "public_ip": args.public_ip,
            "destination_host": args.destination_host,
            "destination_ip": args.destination_ip,
            "protocol": args.protocol,
            "from": args.from_datetime,
            "to": args.to_datetime,
            "limit": args.limit,
        },
    )
    if not events:
        print("No hay eventos de red")
        return
    for event in events:
        destination = event.get("destination_host") or event.get("destination_ip") or ""
        destination_port = event.get("destination_port")
        if destination_port:
            destination = f"{destination}:{destination_port}"
        print(
            f"{event.get('occurred_at', '')} "
            f"device={event.get('device_id', '')} "
            f"protocol={event.get('protocol', '')} "
            f"destination={destination} "
            f"local_ip={event.get('local_ip', '')} "
            f"public_ip={event.get('public_ip', '')}",
        )


def _print_lifecycle_history(settings: AuditorSettings, args: argparse.Namespace) -> None:
    session = _load_required_session(settings, args.company)
    events = _build_auditor_api_client(settings).search_lifecycle_events(
        auditor_session_id=session.auditor_session_id,
        filters={
            "device_id": args.device_id,
            "event_type": args.event_type,
            "from": args.from_datetime,
            "to": args.to_datetime,
            "limit": args.limit,
        },
    )
    if not events:
        print("No hay eventos lifecycle")
        return
    for event in events:
        print(
            f"{event.get('occurred_at', '')} "
            f"device={event.get('device_id', '')} "
            f"type={event.get('event_type', '')} "
            f"reason={event.get('reason', '')}",
        )


def _print_device_movements_history(settings: AuditorSettings, args: argparse.Namespace) -> None:
    session = _load_required_session(settings, args.company)
    movements = _build_auditor_api_client(settings).search_device_movements(
        auditor_session_id=session.auditor_session_id,
        device_id=args.device_id,
        filters={
            "from": args.from_datetime,
            "to": args.to_datetime,
            "limit": args.limit,
        },
    )
    if not movements:
        print("No hay movimientos del dispositivo")
        return
    for movement in movements:
        print(
            f"{movement.get('occurred_at', '')} "
            f"device={movement.get('device_id', args.device_id)} "
            f"local_ip={movement.get('local_ip', '')} "
            f"public_ip={movement.get('public_ip', '')} "
            f"hostname={movement.get('hostname', '')}",
        )


def _print_incident_window(settings: AuditorSettings, args: argparse.Namespace) -> None:
    session = _load_required_session(settings, args.company)
    window = _build_auditor_api_client(settings).query_incident_window(
        auditor_session_id=session.auditor_session_id,
        filters={
            "from": args.from_datetime,
            "to": args.to_datetime,
            "at": args.at,
            "window_seconds": args.window_seconds,
            "limit": args.limit,
        },
    )
    print(f"Window: {window.get('from_datetime', '')} -> {window.get('to_datetime', '')}")
    print(f"Active devices: {len(_list_value(window.get('active_devices')))}")
    print(f"Without report: {len(_list_value(window.get('devices_without_report')))}")
    print(f"Seen after window: {len(_list_value(window.get('devices_seen_after_window')))}")
    print(f"Network events: {len(_list_value(window.get('network_events')))}")
    print(f"Lifecycle events: {len(_list_value(window.get('lifecycle_events')))}")


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _export_json(settings: AuditorSettings, args: argparse.Namespace) -> None:
    session = _load_required_session(settings, args.company)
    export_payload = build_audit_export(
        _build_auditor_api_client(settings),
        session,
        from_datetime=args.from_datetime,
        to_datetime=args.to_datetime,
        device_id=args.device_id,
        limit=args.limit,
    )
    serialized_export = json.dumps(export_payload, indent=2, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"{serialized_export}\n", encoding="utf-8")
        output_path.chmod(0o600)
        network_events = _list_value(export_payload["events"].get("network_events"))
        lifecycle_events = _list_value(export_payload["events"].get("lifecycle_events"))
        device_movements = _list_value(export_payload["events"].get("device_movements"))
        print(
            f"Export JSON: {output_path} "
            f"network={len(network_events)} "
            f"lifecycle={len(lifecycle_events)} "
            f"movements={len(device_movements)}",
        )
        return

    print(serialized_export)


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


def _load_required_session(
    settings: AuditorSettings,
    company_id: str | None = None,
) -> AuditorSessionState:
    session = JsonAuditorSessionStore(settings.session_file).load()
    if session is None:
        raise AuditorStateError("No hay sesion local de auditor; ejecuta access verify")
    if session.is_revoked:
        raise AuditorStateError("La sesion local de auditor esta revocada")
    if session.is_expired():
        raise AuditorStateError("La sesion local de auditor expiro")
    if company_id is not None and session.company_id != company_id:
        raise AuditorStateError("La sesion local pertenece a otra empresa")
    return session


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
