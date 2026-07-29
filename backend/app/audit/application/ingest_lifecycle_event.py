from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from backend.app.audit.application.resolve_audit_company_context import (
    ResolveAuditCompanyContextCommand,
    ResolveAuditCompanyContextUseCase,
)
from backend.app.audit.domain.entities import AgentLifecycleEvent, AgentLifecycleEventType
from backend.app.audit.domain.repositories import AgentLifecycleEventRepository


@dataclass(frozen=True, slots=True)
class IngestAgentLifecycleEventCommand:
    event_type: AgentLifecycleEventType
    occurred_at: datetime
    device_id: str
    company_id: str
    company_device_link_id: str
    hostname: str
    agent_version: str
    local_ip: str | None = None
    public_ip: str | None = None
    reason: str | None = None
    last_seen_at: datetime | None = None
    detected_at: datetime | None = None
    downtime_seconds: int | None = None


class IngestAgentLifecycleEventUseCase:
    def __init__(
        self,
        repository: AgentLifecycleEventRepository,
        company_context_resolver: ResolveAuditCompanyContextUseCase,
    ) -> None:
        self._repository = repository
        self._company_context_resolver = company_context_resolver

    def execute(self, command: IngestAgentLifecycleEventCommand) -> AgentLifecycleEvent:
        link = self._company_context_resolver.execute(
            ResolveAuditCompanyContextCommand(
                company_id=command.company_id,
                company_device_link_id=command.company_device_link_id,
                device_id=command.device_id,
            ),
        )
        event = AgentLifecycleEvent(
            event_id=str(uuid4()),
            event_type=command.event_type,
            occurred_at=command.occurred_at,
            device_id=command.device_id,
            company_id=link.company_id,
            company_device_link_id=link.company_device_link_id,
            hostname=command.hostname,
            agent_version=command.agent_version,
            local_ip=command.local_ip,
            public_ip=command.public_ip,
            reason=command.reason,
            last_seen_at=command.last_seen_at,
            detected_at=command.detected_at,
            downtime_seconds=command.downtime_seconds,
        )
        return self._repository.save(event)
