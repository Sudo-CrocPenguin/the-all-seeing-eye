from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from backend.app.audit.domain.entities import AgentLifecycleEvent, AgentLifecycleEventType
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    AgentLifecycleEventRepository,
)
from backend.app.devices.application.mark_device_seen import (
    MarkDeviceSeenCommand,
    MarkDeviceSeenUseCase,
)
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.time import ensure_aware, utc_now


@dataclass(frozen=True, slots=True)
class RecordAgentActivityCommand:
    device_id: str
    company_id: str
    company_device_link_id: str
    hostname: str
    agent_version: str
    local_ip: str | None = None
    public_ip: str | None = None
    observed_at: datetime | None = None
    detect_recovery: bool = True


class RecordAgentActivityUseCase:
    def __init__(
        self,
        device_repository: DeviceRepository,
        lifecycle_event_repository: AgentLifecycleEventRepository,
    ) -> None:
        self._device_repository = device_repository
        self._lifecycle_event_repository = lifecycle_event_repository

    def execute(self, command: RecordAgentActivityCommand) -> AgentLifecycleEvent | None:
        observed_at = ensure_aware(command.observed_at or utc_now())
        recovered_event = None
        if command.detect_recovery:
            recovered_event = self._record_recovery_if_needed(command, observed_at)

        mark_seen = MarkDeviceSeenUseCase(self._device_repository)
        mark_seen.execute(MarkDeviceSeenCommand(device_id=command.device_id, seen_at=observed_at))
        return recovered_event

    def _record_recovery_if_needed(
        self,
        command: RecordAgentActivityCommand,
        observed_at: datetime,
    ) -> AgentLifecycleEvent | None:
        latest_events = self._lifecycle_event_repository.search(
            AgentLifecycleEventFilters(
                company_id=command.company_id,
                device_id=command.device_id,
                limit=1,
            ),
        )
        if not latest_events:
            return None

        latest_event = latest_events[0]
        if latest_event.event_type is not AgentLifecycleEventType.MISSED_HEARTBEAT:
            return None

        recovered_event = self._build_recovered_event(command, latest_event, observed_at)
        return self._lifecycle_event_repository.save(recovered_event)

    @staticmethod
    def _build_recovered_event(
        command: RecordAgentActivityCommand,
        missed_event: AgentLifecycleEvent,
        observed_at: datetime,
    ) -> AgentLifecycleEvent:
        last_seen_at = missed_event.last_seen_at
        downtime_seconds = missed_event.downtime_seconds
        if last_seen_at is not None:
            downtime_seconds = max(int((observed_at - last_seen_at).total_seconds()), 0)

        return AgentLifecycleEvent(
            event_id=str(uuid4()),
            event_type=AgentLifecycleEventType.RECOVERED,
            occurred_at=observed_at,
            device_id=command.device_id,
            company_id=command.company_id,
            company_device_link_id=command.company_device_link_id,
            hostname=command.hostname,
            agent_version=command.agent_version,
            local_ip=command.local_ip,
            public_ip=command.public_ip,
            reason="agent reported after missed heartbeat",
            last_seen_at=last_seen_at,
            detected_at=observed_at,
            downtime_seconds=downtime_seconds,
        )
