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

DeviceMovementType = Literal[
    "NETWORK_CONNECTION",
    "AGENT_STARTED",
    "AGENT_STOPPING",
    "AGENT_STOPPED",
    "AGENT_HEARTBEAT",
    "AGENT_MISSED_HEARTBEAT",
    "AGENT_RECOVERED",
    "AGENT_CONFIG_CHANGED",
]


@dataclass(frozen=True, slots=True)
class QueryDeviceMovementsCommand:
    company_id: str
    device_id: str
    from_datetime: datetime | None = None
    to_datetime: datetime | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class DeviceMovement:
    event_id: str
    occurred_at: datetime
    created_at: datetime
    movement_type: DeviceMovementType
    device_id: str
    company_id: str
    company_device_link_id: str
    hostname: str
    local_ip: str | None
    public_ip: str | None
    summary: str
    protocol: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    local_username: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    process_executable: str | None = None
    service_name: str | None = None
    network_interface: str | None = None
    connection_status: str | None = None
    lifecycle_reason: str | None = None


class QueryDeviceMovementsUseCase:
    def __init__(
        self,
        network_event_repository: NetworkAuditEventRepository,
        lifecycle_event_repository: AgentLifecycleEventRepository,
    ) -> None:
        self._network_event_repository = network_event_repository
        self._lifecycle_event_repository = lifecycle_event_repository

    def execute(self, command: QueryDeviceMovementsCommand) -> list[DeviceMovement]:
        limit = max(command.limit, 1)
        network_events = self._network_event_repository.search(
            NetworkAuditEventFilters(
                company_id=command.company_id,
                device_id=command.device_id,
                from_datetime=command.from_datetime,
                to_datetime=command.to_datetime,
                limit=limit,
            ),
        )
        lifecycle_events = self._lifecycle_event_repository.search(
            AgentLifecycleEventFilters(
                company_id=command.company_id,
                device_id=command.device_id,
                from_datetime=command.from_datetime,
                to_datetime=command.to_datetime,
                limit=limit,
            ),
        )
        movements = [
            *[_network_event_to_movement(event) for event in network_events],
            *[_lifecycle_event_to_movement(event) for event in lifecycle_events],
        ]
        movements.sort(key=lambda movement: movement.occurred_at, reverse=True)
        return movements[:limit]


def _network_event_to_movement(event: NetworkAuditEvent) -> DeviceMovement:
    return DeviceMovement(
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        movement_type="NETWORK_CONNECTION",
        device_id=event.device_id,
        company_id=event.company_id,
        company_device_link_id=event.company_device_link_id,
        hostname=event.hostname,
        local_ip=event.local_ip,
        public_ip=event.public_ip,
        summary=_network_summary(event),
        protocol=event.protocol,
        destination_host=event.destination_host,
        destination_ip=event.destination_ip,
        destination_port=event.destination_port,
        local_username=event.local_username,
        process_id=event.process_id,
        process_name=event.process_name,
        process_executable=event.process_executable,
        service_name=event.service_name,
        network_interface=event.network_interface,
        connection_status=event.request_metadata.get("connection_status"),
    )


def _lifecycle_event_to_movement(event: AgentLifecycleEvent) -> DeviceMovement:
    return DeviceMovement(
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        created_at=event.created_at,
        movement_type=event.event_type.value,
        device_id=event.device_id,
        company_id=event.company_id,
        company_device_link_id=event.company_device_link_id,
        hostname=event.hostname,
        local_ip=event.local_ip,
        public_ip=event.public_ip,
        summary=_lifecycle_summary(event),
        lifecycle_reason=event.reason,
    )


def _network_summary(event: NetworkAuditEvent) -> str:
    destination = event.service_name or event.destination_host or event.destination_ip
    if destination is None:
        return "Conexion saliente"
    if event.destination_port is None:
        return destination
    return f"{destination}:{event.destination_port}"


def _lifecycle_summary(event: AgentLifecycleEvent) -> str:
    if event.reason:
        return f"{event.event_type.value}: {event.reason}"
    return event.event_type.value
