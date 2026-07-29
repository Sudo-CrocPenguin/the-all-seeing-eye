import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from agent.app.clock import to_iso, utc_now
from agent.app.config import AgentSettings
from agent.app.device_identity import DeviceIdentity, DeviceIdentityCollector
from agent.app.local_queue import LocalAgentRequestQueue, QueuedAuditApiClient
from agent.app.runner import AgentConfigurationError, AgentRunner
from agent.app.state import (
    AgentState,
    AgentStateError,
    JsonAgentStateStore,
    LinkedCompanyState,
)
from agent.app.transport import AgentTransportError, AuditApiClient, InsecureBackendUrlError


class AgentCliApiClient(Protocol):
    def register_device(self, identity: DeviceIdentity) -> dict[str, Any]:
        raise NotImplementedError

    def request_device_enrollment(
        self,
        identity: DeviceIdentity,
        enrollment_code: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def list_device_links(self, device_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def revoke_device_link(
        self,
        *,
        device_id: str,
        company_device_link_id: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def send_lifecycle_event(
        self,
        identity: DeviceIdentity,
        event_type: str,
        occurred_at: str,
        *,
        company_id: str,
        company_device_link_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente corporativo de auditoria de red.")
    _add_runtime_options(parser)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Alias legacy de run-once.",
    )
    parser.add_argument(
        "--identify",
        action="store_true",
        help="Imprime la identidad detectada del dispositivo y termina.",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status", help="Muestra estado local del agente.")
    subparsers.add_parser("companies", help="Lista empresas vinculadas del dispositivo.")

    link_parser = subparsers.add_parser("link", help="Solicita vinculacion con codigo.")
    link_parser.add_argument("--code", required=True, help="Codigo de vinculacion.")

    use_company_parser = subparsers.add_parser(
        "use-company",
        help="Selecciona empresa activa.",
    )
    use_company_parser.add_argument("--company", required=True, help="company_id.")

    subparsers.add_parser("start-recording", help="Enciende registro de red.")
    subparsers.add_parser("stop-recording", help="Apaga registro de red.")

    unlink_parser = subparsers.add_parser("unlink", help="Desvincula una empresa.")
    unlink_parser.add_argument("--company", required=True, help="company_id.")

    subparsers.add_parser("run-once", help="Ejecuta un ciclo y termina.")
    subparsers.add_parser("run", help="Ejecuta el agente continuamente.")
    return parser


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend-url", help="URL base del backend de auditoria.")
    parser.add_argument(
        "--env-file",
        help="Archivo de configuracion KEY=VALUE para ejecutar el agente como servicio.",
    )
    parser.add_argument(
        "--device-id",
        help="Identificador estable del dispositivo. Si se omite, se genera desde el equipo.",
    )
    parser.add_argument(
        "--company-id",
        help="Empresa activa donde se registraran los eventos de auditoria.",
    )
    parser.add_argument(
        "--company-device-link-id",
        help="Vinculo activo empresa-dispositivo para los eventos de auditoria.",
    )
    parser.add_argument("--state-file", help="Ruta del estado local JSON del agente.")
    parser.add_argument("--queue-file", help="Ruta de la cola local JSONL del agente.")
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        help="Intervalo en segundos entre heartbeats.",
    )
    parser.add_argument(
        "--scan-interval",
        type=int,
        help="Intervalo en segundos entre lecturas de conexiones.",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = _settings_from_args(args)

    try:
        if args.identify:
            identity = DeviceIdentityCollector(settings).collect()
            print(json.dumps(asdict(identity), indent=2))
            return

        command = _resolve_command(args)
        if command == "status":
            _print_status(settings)
            return
        if command == "companies":
            _list_companies(settings)
            return
        if command == "link":
            _request_link(settings, args.code)
            return
        if command == "use-company":
            _use_company(settings, args.company)
            return
        if command == "start-recording":
            _start_recording(settings)
            return
        if command == "stop-recording":
            _stop_recording(settings)
            return
        if command == "unlink":
            _unlink_company(settings, args.company)
            return
        if command == "run-once":
            AgentRunner(settings).run_once()
            print(f"Agente ejecuto un ciclo contra {settings.backend_url}")
            return

        AgentRunner(settings).run_forever()
    except (AgentConfigurationError, AgentStateError, AgentTransportError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def _settings_from_args(args: argparse.Namespace) -> AgentSettings:
    settings = AgentSettings.from_environment(args.env_file)
    return AgentSettings(
        backend_url=(args.backend_url or settings.backend_url).rstrip("/"),
        device_id=args.device_id or settings.device_id,
        company_id=args.company_id or settings.company_id,
        company_device_link_id=args.company_device_link_id or settings.company_device_link_id,
        agent_token=settings.agent_token,
        agent_token_header=settings.agent_token_header,
        heartbeat_interval_seconds=args.heartbeat_interval or settings.heartbeat_interval_seconds,
        scan_interval_seconds=args.scan_interval or settings.scan_interval_seconds,
        network_event_dedup_seconds=settings.network_event_dedup_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        request_retry_backoff_seconds=settings.request_retry_backoff_seconds,
        state_file=Path(args.state_file) if args.state_file else settings.state_file,
        queue_file=Path(args.queue_file) if args.queue_file else settings.queue_file,
        service_map_file=settings.service_map_file,
        reverse_dns_enabled=settings.reverse_dns_enabled,
        allow_insecure_transport=settings.allow_insecure_transport,
    )


def _resolve_command(args: argparse.Namespace) -> str | None:
    if args.once:
        return "run-once"
    command = args.command
    return command if isinstance(command, str) else None


def _print_status(settings: AgentSettings) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    state = JsonAgentStateStore(settings.state_file).load()
    active_company = state.active_company
    queue_size = len(LocalAgentRequestQueue(settings.queue_file).read_all())
    backend_status = _backend_status(settings, identity)

    print(f"Device: {identity.hostname}")
    print(f"Device ID: {identity.device_id}")
    print(f"Recording: {_recording_label(settings, state)}")
    print(f"Active company: {_active_company_label(settings, active_company)}")
    print(f"Queue: {queue_size} pending events")
    print(f"Backend: {backend_status}")


def _list_companies(settings: AgentSettings) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state = _sync_linked_companies(
        state_store,
        identity,
        client.list_device_links(identity.device_id),
    )

    if not state.linked_companies:
        print("No hay empresas vinculadas")
        return

    for company in state.linked_companies:
        marker = "*" if _is_active_company(state, company) else " "
        print(f"{marker} {company.company_name} ({company.company_id}) - {company.status}")


def _request_link(settings: AgentSettings, enrollment_code: str) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state_store.save(_load_state_for_identity(state_store, identity, persist_device_id=True))

    client.register_device(identity)
    response = client.request_device_enrollment(identity, enrollment_code)
    if not response:
        print("Solicitud de vinculacion guardada en cola local")
        return

    company_id = response.get("company_id", "")
    status = response.get("status", "")
    print(f"Solicitud de vinculacion enviada: company_id={company_id} status={status}")


def _use_company(settings: AgentSettings, company_id: str) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state = _load_state_for_identity(state_store, identity, persist_device_id=True)
    if state.find_active_company(company_id) is None:
        state = _sync_linked_companies(
            state_store,
            identity,
            client.list_device_links(identity.device_id),
        )

    selected_state = state.select_company(company_id)
    state_store.save(selected_state)
    active_company = _require_active_company(selected_state)
    _send_lifecycle_for_company(
        client,
        identity,
        active_company,
        "AGENT_CONFIG_CHANGED",
        reason="active company changed",
    )
    print(f"Empresa activa: {active_company.company_name} ({active_company.company_id})")


def _start_recording(settings: AgentSettings) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state = _load_state_for_identity(state_store, identity, persist_device_id=True)
    active_company = _require_active_company(state)
    saved_state = state_store.save(state.with_recording_enabled(True))
    _send_lifecycle_for_company(
        client,
        identity,
        active_company,
        "AGENT_CONFIG_CHANGED",
        reason="recording enabled by local user",
    )
    print(f"Recording: {_recording_label(settings, saved_state)}")


def _stop_recording(settings: AgentSettings) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state = _load_state_for_identity(state_store, identity, persist_device_id=True)
    active_company = _require_active_company(state)
    reason = "recording disabled by local user"
    try:
        _send_lifecycle_for_company(
            client,
            identity,
            active_company,
            "AGENT_STOPPING",
            reason=reason,
        )
        _send_lifecycle_for_company(
            client,
            identity,
            active_company,
            "AGENT_STOPPED",
            reason=reason,
        )
    finally:
        saved_state = state_store.save(state.with_recording_enabled(False))
    print(f"Recording: {_recording_label(settings, saved_state)}")


def _unlink_company(settings: AgentSettings, company_id: str) -> None:
    identity = DeviceIdentityCollector(settings).collect()
    client = _build_agent_api_client(settings)
    state_store = JsonAgentStateStore(settings.state_file)
    state = _load_state_for_identity(state_store, identity, persist_device_id=True)
    linked_company = _require_linked_company(state, company_id)

    _send_lifecycle_for_company(
        client,
        identity,
        linked_company,
        "AGENT_CONFIG_CHANGED",
        reason="company link revoked by device",
    )
    client.revoke_device_link(
        device_id=identity.device_id,
        company_device_link_id=linked_company.company_device_link_id,
    )
    state_store.save(state.remove_company(company_id))
    print(f"Empresa desvinculada: {linked_company.company_name} ({linked_company.company_id})")


def _build_agent_api_client(settings: AgentSettings) -> AgentCliApiClient:
    if not settings.agent_token:
        raise AgentConfigurationError("AGENT_TOKEN es obligatorio para operar contra el backend")
    try:
        client = AuditApiClient(
            settings.backend_url,
            agent_token=settings.agent_token,
            agent_token_header=settings.agent_token_header,
            timeout_seconds=settings.request_timeout_seconds,
            allow_insecure_transport=settings.allow_insecure_transport,
        )
    except InsecureBackendUrlError as exc:
        raise AgentConfigurationError(str(exc)) from exc

    return QueuedAuditApiClient.from_audit_api_client(
        client,
        settings.queue_file,
        retry_backoff_seconds=settings.request_retry_backoff_seconds,
    )


def _sync_linked_companies(
    state_store: JsonAgentStateStore,
    identity: DeviceIdentity,
    raw_links: list[dict[str, Any]],
) -> AgentState:
    state = _load_state_for_identity(state_store, identity, persist_device_id=True)
    linked_companies = tuple(
        sorted(
            (_linked_company_from_response(raw_link) for raw_link in raw_links),
            key=lambda company: company.company_name.lower(),
        ),
    )
    return state_store.save(state.replace_linked_companies(linked_companies))


def _load_state_for_identity(
    state_store: JsonAgentStateStore,
    identity: DeviceIdentity,
    *,
    persist_device_id: bool,
) -> AgentState:
    state = state_store.load()
    if state.device_id is not None and state.device_id != identity.device_id:
        raise AgentConfigurationError(
            "El estado local pertenece a otro dispositivo; revise AGENT_STATE_FILE",
        )
    if persist_device_id and state.device_id is None:
        return state_store.save(state.with_device_id(identity.device_id))
    return state


def _linked_company_from_response(raw_link: dict[str, Any]) -> LinkedCompanyState:
    return LinkedCompanyState(
        company_id=_required_text(raw_link, "company_id"),
        company_device_link_id=_required_text(raw_link, "company_device_link_id"),
        company_name=_required_text(raw_link, "company_name"),
        status=_required_text(raw_link, "status"),
        linked_at=_optional_text(raw_link, "linked_at"),
        revoked_at=_optional_text(raw_link, "revoked_at"),
    )


def _required_text(raw_value: dict[str, Any], field_name: str) -> str:
    value = _optional_text(raw_value, field_name)
    if value is None:
        raise AgentStateError(f"Respuesta backend sin {field_name}")
    return value


def _optional_text(raw_value: dict[str, Any], field_name: str) -> str | None:
    value = raw_value.get(field_name)
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value)


def _require_active_company(state: AgentState) -> LinkedCompanyState:
    active_company = state.active_company
    if active_company is None or not active_company.is_active:
        raise AgentStateError("Selecciona una empresa activa antes de operar")
    return active_company


def _require_linked_company(state: AgentState, company_id: str) -> LinkedCompanyState:
    for company in state.linked_companies:
        if company.company_id == company_id:
            return company
    raise AgentStateError("La empresa no esta vinculada a este dispositivo")


def _send_lifecycle_for_company(
    client: AgentCliApiClient,
    identity: DeviceIdentity,
    company: LinkedCompanyState,
    event_type: str,
    *,
    reason: str,
) -> dict[str, Any]:
    return client.send_lifecycle_event(
        identity,
        event_type,
        to_iso(utc_now()),
        company_id=company.company_id,
        company_device_link_id=company.company_device_link_id,
        reason=reason,
    )


def _backend_status(settings: AgentSettings, identity: DeviceIdentity) -> str:
    if not settings.agent_token:
        return "not configured"
    try:
        _build_agent_api_client(settings).list_device_links(identity.device_id)
    except (AgentConfigurationError, AgentTransportError):
        return "unreachable"
    return "reachable"


def _recording_label(settings: AgentSettings, state: AgentState) -> str:
    if state.active_company is not None:
        return "ON" if state.recording_enabled else "OFF"
    if settings.company_id and settings.company_device_link_id:
        return "ON"
    return "OFF"


def _active_company_label(
    settings: AgentSettings,
    active_company: LinkedCompanyState | None,
) -> str:
    if active_company is not None:
        return f"{active_company.company_name} ({active_company.company_id})"
    if settings.company_id:
        return f"{settings.company_id} (env fallback)"
    return "none"


def _is_active_company(state: AgentState, company: LinkedCompanyState) -> bool:
    return (
        state.active_company_id == company.company_id
        and state.active_company_device_link_id == company.company_device_link_id
    )


if __name__ == "__main__":
    main()
