from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backend.app.audit.domain.entities import AgentLifecycleEvent, NetworkAuditEvent


@dataclass(frozen=True, slots=True)
class NetworkAuditEventFilters:
    company_id: str | None = None
    company_device_link_id: str | None = None
    device_id: str | None = None
    local_ip: str | None = None
    public_ip: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    protocol: str | None = None
    from_datetime: datetime | None = None
    to_datetime: datetime | None = None
    limit: int = 100


@dataclass(frozen=True, slots=True)
class AgentLifecycleEventFilters:
    company_id: str | None = None
    company_device_link_id: str | None = None
    device_id: str | None = None
    event_type: str | None = None
    from_datetime: datetime | None = None
    to_datetime: datetime | None = None
    limit: int = 100


class NetworkAuditEventRepository(Protocol):
    def save(self, event: NetworkAuditEvent) -> NetworkAuditEvent:
        raise NotImplementedError

    def search(self, filters: NetworkAuditEventFilters) -> list[NetworkAuditEvent]:
        raise NotImplementedError

    def list_device_ids(self, filters: NetworkAuditEventFilters) -> set[str]:
        raise NotImplementedError

    def latest_seen_at_by_device(self, filters: NetworkAuditEventFilters) -> dict[str, datetime]:
        raise NotImplementedError


class AgentLifecycleEventRepository(Protocol):
    def save(self, event: AgentLifecycleEvent) -> AgentLifecycleEvent:
        raise NotImplementedError

    def search(self, filters: AgentLifecycleEventFilters) -> list[AgentLifecycleEvent]:
        raise NotImplementedError

    def list_device_ids(self, filters: AgentLifecycleEventFilters) -> set[str]:
        raise NotImplementedError

    def latest_seen_at_by_device(
        self,
        filters: AgentLifecycleEventFilters,
    ) -> dict[str, datetime]:
        raise NotImplementedError
