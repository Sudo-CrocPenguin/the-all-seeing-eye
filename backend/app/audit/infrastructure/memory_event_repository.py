from datetime import datetime
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
        items = self._filter_items(filters)

        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return items[: max(filters.limit, 0)]

    def list_device_ids(self, filters: NetworkAuditEventFilters) -> set[str]:
        return {item.device_id for item in self._filter_items(filters)}

    def latest_seen_at_by_device(self, filters: NetworkAuditEventFilters) -> dict[str, datetime]:
        latest_seen: dict[str, datetime] = {}
        for item in self._filter_items(filters):
            occurred_at = ensure_aware(item.occurred_at)
            current = latest_seen.get(item.device_id)
            if current is None or occurred_at > current:
                latest_seen[item.device_id] = occurred_at
        return latest_seen

    def _filter_items(self, filters: NetworkAuditEventFilters) -> list[NetworkAuditEvent]:
        with self._lock:
            items = list(self._items)

        if filters.company_id:
            items = [item for item in items if item.company_id == filters.company_id]
        if filters.company_device_link_id:
            items = [
                item
                for item in items
                if item.company_device_link_id == filters.company_device_link_id
            ]
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

        return items


class InMemoryAgentLifecycleEventRepository:
    def __init__(self) -> None:
        self._items: list[AgentLifecycleEvent] = []
        self._lock = Lock()

    def save(self, event: AgentLifecycleEvent) -> AgentLifecycleEvent:
        with self._lock:
            self._items.append(event)
        return event

    def search(self, filters: AgentLifecycleEventFilters) -> list[AgentLifecycleEvent]:
        items = self._filter_items(filters)

        items.sort(key=lambda item: item.occurred_at, reverse=True)
        return items[: max(filters.limit, 0)]

    def list_device_ids(self, filters: AgentLifecycleEventFilters) -> set[str]:
        return {item.device_id for item in self._filter_items(filters)}

    def latest_seen_at_by_device(
        self,
        filters: AgentLifecycleEventFilters,
    ) -> dict[str, datetime]:
        latest_seen: dict[str, datetime] = {}
        for item in self._filter_items(filters):
            occurred_at = ensure_aware(item.occurred_at)
            current = latest_seen.get(item.device_id)
            if current is None or occurred_at > current:
                latest_seen[item.device_id] = occurred_at
        return latest_seen

    def _filter_items(self, filters: AgentLifecycleEventFilters) -> list[AgentLifecycleEvent]:
        with self._lock:
            items = list(self._items)

        if filters.company_id:
            items = [item for item in items if item.company_id == filters.company_id]
        if filters.company_device_link_id:
            items = [
                item
                for item in items
                if item.company_device_link_id == filters.company_device_link_id
            ]
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

        return items
