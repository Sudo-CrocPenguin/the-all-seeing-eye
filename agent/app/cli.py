import argparse
import json
import sys
from dataclasses import asdict

from agent.app.config import AgentSettings
from agent.app.device_identity import DeviceIdentityCollector
from agent.app.runner import AgentConfigurationError, AgentRunner
from agent.app.transport import AgentTransportError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente corporativo de auditoria de red.")
    parser.add_argument(
        "--backend-url",
        help="URL base del backend de auditoria.",
    )
    parser.add_argument(
        "--env-file",
        help="Archivo de configuracion KEY=VALUE para ejecutar el agente como servicio.",
    )
    parser.add_argument(
        "--device-id",
        help="Identificador estable del dispositivo. Si se omite, se genera desde el equipo.",
    )
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
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta un ciclo de registro y recoleccion, luego termina.",
    )
    parser.add_argument(
        "--identify",
        action="store_true",
        help="Imprime la identidad detectada del dispositivo y termina.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = AgentSettings.from_environment(args.env_file)
    settings = AgentSettings(
        backend_url=(args.backend_url or settings.backend_url).rstrip("/"),
        device_id=args.device_id or settings.device_id,
        agent_token=settings.agent_token,
        agent_token_header=settings.agent_token_header,
        heartbeat_interval_seconds=args.heartbeat_interval or settings.heartbeat_interval_seconds,
        scan_interval_seconds=args.scan_interval or settings.scan_interval_seconds,
        network_event_dedup_seconds=settings.network_event_dedup_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
        request_retry_backoff_seconds=settings.request_retry_backoff_seconds,
        queue_file=settings.queue_file,
    )

    if args.identify:
        identity = DeviceIdentityCollector(settings).collect()
        print(json.dumps(asdict(identity), indent=2))
        return

    try:
        if args.once:
            AgentRunner(settings).run_once()
            print(f"Agente ejecuto un ciclo contra {settings.backend_url}")
            return

        AgentRunner(settings).run_forever()
    except (AgentConfigurationError, AgentTransportError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
