from threading import Lock

from backend.app.audit.domain.entities import AgentLifecycleEvent, NetworkAuditEvent
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    NetworkAuditEventFilters,
)
from backend.app.shared.time import ensure_aware


class InMemoryNetworkAuditEventRepository:
    def __init__(self) -> None:
        self._items: list[NetworkAuditEvent] = []
        self._lock = Lock()

    def save(self, event: NetworkAuditEvent) -> NetworkAuditEvent:
        with self._lock:
            self._items.append(event)
        return event

    def search(self, filters: NetworkAuditEventFilters) -> list[NetworkAuditEvent]:
        with self._lock:
            items = list(self._items)

        if filters.device_id:
            items = [item for item in items if item.device_id == filters.device_id]
        if filters.local_ip:
            items = [item for item in items if item.local_ip == filters.local_ip]
        if filters.public_ip:
            items = [item for item in items if item.public_ip == filters.public_ip]
        if filters.destination_host:
            items = [item for item in items if item.destination_host == filters.destination_host]
        if filters.destination_ip:
            items = [item for item in items if item.destination_ip == filters.destination_ip]
        if filters.protocol:
            protocol = filters.protocol.upper()
            items = [item for item in items if item.protocol == protocol]
        if filters.from_datetime:
            from_datetime = ensure_aware(filters.from_datetime)
            items = [item for item in items if item.occurred_at >= from_datetime]
        if filters.to_datetime:
            to_datetime = ensure_aware(filters.to_datetime)
            items = [item for item in items if item.occurred_at <= to_datetime]

        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return items[: max(filters.limit, 0)]


class InMemoryAgentLifecycleEventRepository:
    def __init__(self) -> None:
        self._items: list[AgentLifecycleEvent] = []
        self._lock = Lock()

    def save(self, event: AgentLifecycleEvent) -> AgentLifecycleEvent:
        with self._lock:
            self._items.append(event)
        return event

    def search(self, filters: AgentLifecycleEventFilters) -> list[AgentLifecycleEvent]:
        with self._lock:
            items = list(self._items)

        if filters.device_id:
            items = [item for item in items if item.device_id == filters.device_id]
        if filters.event_type:
            items = [item for item in items if item.event_type.value == filters.event_type]
        if filters.from_datetime:
            from_datetime = ensure_aware(filters.from_datetime)
            items = [item for item in items if item.occurred_at >= from_datetime]
        if filters.to_datetime:
            to_datetime = ensure_aware(filters.to_datetime)
            items = [item for item in items if item.occurred_at <= to_datetime]

        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return items[: max(filters.limit, 0)]

