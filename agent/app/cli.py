import argparse

from agent.app.config import AgentSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agente corporativo de auditoria de red.")
    parser.add_argument(
        "--backend-url",
        help="URL base del backend de auditoria.",
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = AgentSettings.from_environment()
    settings = AgentSettings(
        backend_url=(args.backend_url or settings.backend_url).rstrip("/"),
        device_id=args.device_id or settings.device_id,
        heartbeat_interval_seconds=args.heartbeat_interval or settings.heartbeat_interval_seconds,
        scan_interval_seconds=args.scan_interval or settings.scan_interval_seconds,
        network_event_dedup_seconds=settings.network_event_dedup_seconds,
        request_timeout_seconds=settings.request_timeout_seconds,
    )

    if args.once:
        print(f"Agente configurado para {settings.backend_url}")
        return

    print(f"Agente configurado para {settings.backend_url}")


if __name__ == "__main__":
    main()
