import asyncio
import logging

from backend.app.audit.application.detect_missed_heartbeats import (
    DetectMissedHeartbeatsCommand,
    DetectMissedHeartbeatsUseCase,
)
from backend.app.shared.container import RuntimeContainer

LOGGER = logging.getLogger(__name__)


def detect_missed_heartbeats_once(runtime_container: RuntimeContainer) -> int:
    if runtime_container.settings.persistence_backend == "memory":
        app_container = runtime_container.build_memory_container()
        use_case = DetectMissedHeartbeatsUseCase(
            app_container.device_repository,
            app_container.lifecycle_event_repository,
            app_container.company_device_link_repository,
        )
        events = use_case.execute(
            DetectMissedHeartbeatsCommand(
                timeout_seconds=runtime_container.settings.agent_heartbeat_timeout_seconds,
            ),
        )
        return len(events)

    if runtime_container.session_factory is None:
        raise RuntimeError("La persistencia SQLAlchemy no tiene session_factory configurado")

    with runtime_container.session_factory() as session:
        try:
            app_container = runtime_container.build_sqlalchemy_container(session)
            use_case = DetectMissedHeartbeatsUseCase(
                app_container.device_repository,
                app_container.lifecycle_event_repository,
                app_container.company_device_link_repository,
            )
            events = use_case.execute(
                DetectMissedHeartbeatsCommand(
                    timeout_seconds=runtime_container.settings.agent_heartbeat_timeout_seconds,
                ),
            )
            session.commit()
            return len(events)
        except Exception:
            session.rollback()
            raise


async def missed_heartbeat_scheduler_loop(runtime_container: RuntimeContainer) -> None:
    interval_seconds = max(
        runtime_container.settings.missed_heartbeat_scheduler_interval_seconds,
        1,
    )
    while True:
        try:
            await asyncio.to_thread(detect_missed_heartbeats_once, runtime_container)
        except Exception:
            LOGGER.exception("Fallo el detector programado de heartbeats ausentes")

        await asyncio.sleep(interval_seconds)
