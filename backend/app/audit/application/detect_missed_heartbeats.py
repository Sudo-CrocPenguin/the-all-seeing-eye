from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from backend.app.audit.domain.entities import AgentLifecycleEvent, AgentLifecycleEventType
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    AgentLifecycleEventRepository,
)
from backend.app.companies.domain.entities import CompanyDeviceLink
from backend.app.companies.domain.repositories import CompanyDeviceLinkRepository
from backend.app.devices.domain.entities import Device
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.time import ensure_aware, utc_now

_EVENT_TYPES_THAT_ALREADY_EXPLAIN_ABSENCE = {
    AgentLifecycleEventType.MISSED_HEARTBEAT.value,
    AgentLifecycleEventType.STOPPING.value,
    AgentLifecycleEventType.STOPPED.value,
}


@dataclass(frozen=True, slots=True)
class DetectMissedHeartbeatsCommand:
    timeout_seconds: int
    detected_at: datetime | None = None


class DetectMissedHeartbeatsUseCase:
    def __init__(
        self,
        device_repository: DeviceRepository,
        lifecycle_event_repository: AgentLifecycleEventRepository,
        company_device_link_repository: CompanyDeviceLinkRepository,
    ) -> None:
        self._device_repository = device_repository
        self._lifecycle_event_repository = lifecycle_event_repository
        self._company_device_link_repository = company_device_link_repository

    def execute(self, command: DetectMissedHeartbeatsCommand) -> list[AgentLifecycleEvent]:
        detected_at = ensure_aware(command.detected_at or utc_now())
        timeout_seconds = max(command.timeout_seconds, 1)
        stale_before = detected_at - timedelta(seconds=timeout_seconds)
        events: list[AgentLifecycleEvent] = []

        devices_by_id = {device.device_id: device for device in self._device_repository.list_all()}
        for link in self._company_device_link_repository.list_active():
            device = devices_by_id.get(link.device_id)
            if device is None:
                continue
            if not self._should_mark_missed(device, stale_before):
                continue
            if self._latest_event_explains_absence(
                company_id=link.company_id,
                device_id=device.device_id,
            ):
                continue

            event = self._build_missed_event(device, link, detected_at)
            events.append(self._lifecycle_event_repository.save(event))

        return events

    @staticmethod
    def _should_mark_missed(device: Device, stale_before: datetime) -> bool:
        if device.last_seen_at is None:
            return False
        return ensure_aware(device.last_seen_at) < stale_before

    def _latest_event_explains_absence(self, *, company_id: str, device_id: str) -> bool:
        latest_events = self._lifecycle_event_repository.search(
            AgentLifecycleEventFilters(
                company_id=company_id,
                device_id=device_id,
                limit=1,
            ),
        )
        if not latest_events:
            return False
        return latest_events[0].event_type.value in _EVENT_TYPES_THAT_ALREADY_EXPLAIN_ABSENCE

    @staticmethod
    def _build_missed_event(
        device: Device,
        link: CompanyDeviceLink,
        detected_at: datetime,
    ) -> AgentLifecycleEvent:
        last_seen_at = ensure_aware(device.last_seen_at) if device.last_seen_at else None
        downtime_seconds = None
        if last_seen_at is not None:
            downtime_seconds = max(int((detected_at - last_seen_at).total_seconds()), 0)

        return AgentLifecycleEvent(
            event_id=str(uuid4()),
            event_type=AgentLifecycleEventType.MISSED_HEARTBEAT,
            occurred_at=detected_at,
            device_id=device.device_id,
            company_id=link.company_id,
            company_device_link_id=link.company_device_link_id,
            hostname=device.hostname,
            agent_version=device.agent_version,
            reason="agent heartbeat timeout exceeded",
            last_seen_at=last_seen_at,
            detected_at=detected_at,
            downtime_seconds=downtime_seconds,
        )
