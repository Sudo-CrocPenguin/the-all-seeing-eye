from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from backend.app.audit.domain.entities import AgentLifecycleEvent, AgentLifecycleEventType
from backend.app.audit.domain.repositories import AgentLifecycleEventRepository


@dataclass(frozen=True, slots=True)
class IngestAgentLifecycleEventCommand:
    event_type: AgentLifecycleEventType
    occurred_at: datetime
    device_id: str
    hostname: str
    agent_version: str
    local_ip: str | None = None
    public_ip: str | None = None
    reason: str | None = None
    last_seen_at: datetime | None = None
    detected_at: datetime | None = None
    downtime_seconds: int | None = None


class IngestAgentLifecycleEventUseCase:
    def __init__(self, repository: AgentLifecycleEventRepository) -> None:
        self._repository = repository

    def execute(self, command: IngestAgentLifecycleEventCommand) -> AgentLifecycleEvent:
        event = AgentLifecycleEvent(
            event_id=str(uuid4()),
            event_type=command.event_type,
            occurred_at=command.occurred_at,
            device_id=command.device_id,
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

