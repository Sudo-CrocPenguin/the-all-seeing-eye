from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from backend.app.audit.domain.entities import AgentLifecycleEvent, NetworkAuditEvent
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    AgentLifecycleEventRepository,
    NetworkAuditEventFilters,
    NetworkAuditEventRepository,
)
from backend.app.companies.domain.repositories import CompanyDeviceLinkRepository
from backend.app.devices.domain.entities import Device
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.domain import DomainValidationError
from backend.app.shared.time import ensure_aware

IncidentDeviceStatusValue = Literal[
    "ACTIVE_IN_WINDOW",
    "WITHOUT_REPORT_BEFORE_WINDOW",
    "SEEN_AFTER_WINDOW",
]


@dataclass(frozen=True, slots=True)
class QueryIncidentWindowCommand:
    company_id: str
    from_datetime: datetime
    to_datetime: datetime
    limit: int = 500


@dataclass(frozen=True, slots=True)
class IncidentDeviceStatus:
    device_id: str
    hostname: str
    os_name: str | None
    agent_version: str | None
    registered_at: datetime | None
    last_seen_at: datetime | None
    status: IncidentDeviceStatusValue


@dataclass(frozen=True, slots=True)
class IncidentWindow:
    from_datetime: datetime
    to_datetime: datetime
    active_devices: list[IncidentDeviceStatus]
    devices_without_report: list[IncidentDeviceStatus]
    devices_seen_after_window: list[IncidentDeviceStatus]
    network_events: list[NetworkAuditEvent]
    lifecycle_events: list[AgentLifecycleEvent]


class QueryIncidentWindowUseCase:
    def __init__(
        self,
        device_repository: DeviceRepository,
        network_event_repository: NetworkAuditEventRepository,
        lifecycle_event_repository: AgentLifecycleEventRepository,
        company_device_link_repository: CompanyDeviceLinkRepository,
    ) -> None:
        self._device_repository = device_repository
        self._network_event_repository = network_event_repository
        self._lifecycle_event_repository = lifecycle_event_repository
        self._company_device_link_repository = company_device_link_repository

    def execute(self, command: QueryIncidentWindowCommand) -> IncidentWindow:
        from_datetime = ensure_aware(command.from_datetime)
        to_datetime = ensure_aware(command.to_datetime)
        if from_datetime > to_datetime:
            raise DomainValidationError("from no puede ser mayor que to")

        limit = max(command.limit, 1)
        network_filters = NetworkAuditEventFilters(
            company_id=command.company_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            limit=limit,
        )
        lifecycle_filters = AgentLifecycleEventFilters(
            company_id=command.company_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            limit=limit,
        )
        network_events = self._network_event_repository.search(
            network_filters,
        )
        lifecycle_events = self._lifecycle_event_repository.search(
            lifecycle_filters,
        )
        active_device_ids = (
            self._network_event_repository.list_device_ids(network_filters)
            | self._lifecycle_event_repository.list_device_ids(lifecycle_filters)
        )
        company_device_ids = {
            link.device_id
            for link in self._company_device_link_repository.list_by_company(command.company_id)
        }
        device_statuses = _build_device_statuses(
            devices=[
                device
                for device in self._device_repository.list_all()
                if device.device_id in company_device_ids
            ],
            network_events=network_events,
            lifecycle_events=lifecycle_events,
            active_device_ids=active_device_ids,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

        return IncidentWindow(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            active_devices=[
                status
                for status in device_statuses
                if status.status == "ACTIVE_IN_WINDOW"
            ],
            devices_without_report=[
                status
                for status in device_statuses
                if status.status == "WITHOUT_REPORT_BEFORE_WINDOW"
            ],
            devices_seen_after_window=[
                status
                for status in device_statuses
                if status.status == "SEEN_AFTER_WINDOW"
            ],
            network_events=network_events,
            lifecycle_events=lifecycle_events,
        )


def _build_device_statuses(
    *,
    devices: list[Device],
    network_events: list[NetworkAuditEvent],
    lifecycle_events: list[AgentLifecycleEvent],
    active_device_ids: set[str],
    from_datetime: datetime,
    to_datetime: datetime,
) -> list[IncidentDeviceStatus]:
    combined_events = _combine_events(network_events, lifecycle_events)
    events_by_device = _latest_event_by_device(combined_events)
    registered_devices = {device.device_id: device for device in devices}
    device_ids = set(registered_devices) | active_device_ids

    statuses = [
        _build_device_status(
            device_id=device_id,
            device=registered_devices.get(device_id),
            latest_event=events_by_device.get(device_id),
            has_window_event=device_id in active_device_ids,
            from_datetime=from_datetime,
        )
        for device_id in device_ids
        if _is_relevant_device(
            registered_devices.get(device_id),
            device_id,
            active_device_ids,
            to_datetime,
        )
    ]
    statuses.sort(key=lambda item: (item.hostname.lower(), item.device_id))
    return statuses


def _combine_events(
    network_events: list[NetworkAuditEvent],
    lifecycle_events: list[AgentLifecycleEvent],
) -> list[NetworkAuditEvent | AgentLifecycleEvent]:
    combined_events: list[NetworkAuditEvent | AgentLifecycleEvent] = []
    combined_events.extend(network_events)
    combined_events.extend(lifecycle_events)
    return combined_events


def _latest_event_by_device(
    events: list[NetworkAuditEvent | AgentLifecycleEvent],
) -> dict[str, NetworkAuditEvent | AgentLifecycleEvent]:
    latest_events: dict[str, NetworkAuditEvent | AgentLifecycleEvent] = {}
    for event in events:
        current = latest_events.get(event.device_id)
        if current is None or event.occurred_at > current.occurred_at:
            latest_events[event.device_id] = event
    return latest_events


def _build_device_status(
    *,
    device_id: str,
    device: Device | None,
    latest_event: NetworkAuditEvent | AgentLifecycleEvent | None,
    has_window_event: bool,
    from_datetime: datetime,
) -> IncidentDeviceStatus:
    last_seen_at = ensure_aware(device.last_seen_at) if device and device.last_seen_at else None
    if has_window_event:
        status: IncidentDeviceStatusValue = "ACTIVE_IN_WINDOW"
    elif last_seen_at is None or last_seen_at < from_datetime:
        status = "WITHOUT_REPORT_BEFORE_WINDOW"
    else:
        status = "SEEN_AFTER_WINDOW"

    return IncidentDeviceStatus(
        device_id=device_id,
        hostname=_device_hostname(device, latest_event, device_id),
        os_name=_device_os_name(device, latest_event),
        agent_version=_device_agent_version(device, latest_event),
        registered_at=ensure_aware(device.registered_at) if device else None,
        last_seen_at=last_seen_at,
        status=status,
    )


def _is_relevant_device(
    device: Device | None,
    device_id: str,
    active_device_ids: set[str],
    to_datetime: datetime,
) -> bool:
    if device_id in active_device_ids:
        return True
    if device is None:
        return False
    return ensure_aware(device.registered_at) <= to_datetime


def _device_hostname(
    device: Device | None,
    latest_event: NetworkAuditEvent | AgentLifecycleEvent | None,
    device_id: str,
) -> str:
    if device is not None:
        return device.hostname
    if latest_event is not None:
        return latest_event.hostname
    return device_id


def _device_os_name(
    device: Device | None,
    latest_event: NetworkAuditEvent | AgentLifecycleEvent | None,
) -> str | None:
    if device is not None:
        return device.os_name
    if isinstance(latest_event, NetworkAuditEvent):
        return latest_event.os_name
    return None


def _device_agent_version(
    device: Device | None,
    latest_event: NetworkAuditEvent | AgentLifecycleEvent | None,
) -> str | None:
    if device is not None:
        return device.agent_version
    if latest_event is not None:
        return latest_event.agent_version
    return None
