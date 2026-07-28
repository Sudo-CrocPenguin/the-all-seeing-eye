from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.app.audit.application.ingest_lifecycle_event import (
    IngestAgentLifecycleEventCommand,
)
from backend.app.audit.application.ingest_network_event import IngestNetworkAuditEventCommand
from backend.app.audit.domain.entities import (
    AgentLifecycleEvent,
    AgentLifecycleEventType,
    NetworkAuditEvent,
)


class AgentLifecycleEventTypeRequest(StrEnum):
    STARTED = "AGENT_STARTED"
    STOPPING = "AGENT_STOPPING"
    STOPPED = "AGENT_STOPPED"
    HEARTBEAT = "AGENT_HEARTBEAT"
    MISSED_HEARTBEAT = "AGENT_MISSED_HEARTBEAT"
    RECOVERED = "AGENT_RECOVERED"
    CONFIG_CHANGED = "AGENT_CONFIG_CHANGED"


class NetworkAuditEventRequest(BaseModel):
    occurred_at: datetime
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    protocol: str
    local_ip: str | None = None
    public_ip: str | None = None
    destination_host: str | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    http_method: str | None = None
    http_status_code: int | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    network_interface: str | None = None
    mac_address: str | None = None
    local_username: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    process_executable: str | None = None
    service_name: str | None = None
    request_metadata: dict[str, str] = Field(default_factory=dict)
    response_metadata: dict[str, str] = Field(default_factory=dict)

    def to_command(self, observed_public_ip: str | None = None) -> IngestNetworkAuditEventCommand:
        return IngestNetworkAuditEventCommand(
            occurred_at=self.occurred_at,
            device_id=self.device_id,
            hostname=self.hostname,
            os_name=self.os_name,
            agent_version=self.agent_version,
            protocol=self.protocol,
            local_ip=self.local_ip,
            public_ip=self.public_ip or observed_public_ip,
            destination_host=self.destination_host,
            destination_ip=self.destination_ip,
            destination_port=self.destination_port,
            http_method=self.http_method,
            http_status_code=self.http_status_code,
            bytes_sent=self.bytes_sent,
            bytes_received=self.bytes_received,
            network_interface=self.network_interface,
            mac_address=self.mac_address,
            local_username=self.local_username,
            process_id=self.process_id,
            process_name=self.process_name,
            process_executable=self.process_executable,
            service_name=self.service_name,
            request_metadata=self.request_metadata,
            response_metadata=self.response_metadata,
        )


class NetworkAuditEventResponse(BaseModel):
    event_id: str
    occurred_at: datetime
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    protocol: str
    local_ip: str | None
    public_ip: str | None
    destination_host: str | None
    destination_ip: str | None
    destination_port: int | None
    http_method: str | None
    http_status_code: int | None
    bytes_sent: int
    bytes_received: int
    network_interface: str | None
    mac_address: str | None
    local_username: str | None
    process_id: int | None
    process_name: str | None
    process_executable: str | None
    service_name: str | None
    request_metadata: dict[str, str]
    response_metadata: dict[str, str]
    created_at: datetime

    @classmethod
    def from_domain(cls, event: NetworkAuditEvent) -> "NetworkAuditEventResponse":
        return cls(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            device_id=event.device_id,
            hostname=event.hostname,
            os_name=event.os_name,
            agent_version=event.agent_version,
            protocol=event.protocol,
            local_ip=event.local_ip,
            public_ip=event.public_ip,
            destination_host=event.destination_host,
            destination_ip=event.destination_ip,
            destination_port=event.destination_port,
            http_method=event.http_method,
            http_status_code=event.http_status_code,
            bytes_sent=event.bytes_sent,
            bytes_received=event.bytes_received,
            network_interface=event.network_interface,
            mac_address=event.mac_address,
            local_username=event.local_username,
            process_id=event.process_id,
            process_name=event.process_name,
            process_executable=event.process_executable,
            service_name=event.service_name,
            request_metadata=event.request_metadata,
            response_metadata=event.response_metadata,
            created_at=event.created_at,
        )


class AgentLifecycleEventRequest(BaseModel):
    event_type: AgentLifecycleEventTypeRequest
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

    def to_command(self, observed_public_ip: str | None = None) -> IngestAgentLifecycleEventCommand:
        return IngestAgentLifecycleEventCommand(
            event_type=AgentLifecycleEventType(self.event_type.value),
            occurred_at=self.occurred_at,
            device_id=self.device_id,
            hostname=self.hostname,
            agent_version=self.agent_version,
            local_ip=self.local_ip,
            public_ip=self.public_ip or observed_public_ip,
            reason=self.reason,
            last_seen_at=self.last_seen_at,
            detected_at=self.detected_at,
            downtime_seconds=self.downtime_seconds,
        )


class AgentLifecycleEventResponse(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    device_id: str
    hostname: str
    agent_version: str
    local_ip: str | None
    public_ip: str | None
    reason: str | None
    last_seen_at: datetime | None
    detected_at: datetime | None
    downtime_seconds: int | None
    created_at: datetime

    @classmethod
    def from_domain(cls, event: AgentLifecycleEvent) -> "AgentLifecycleEventResponse":
        return cls(
            event_id=event.event_id,
            event_type=event.event_type.value,
            occurred_at=event.occurred_at,
            device_id=event.device_id,
            hostname=event.hostname,
            agent_version=event.agent_version,
            local_ip=event.local_ip,
            public_ip=event.public_ip,
            reason=event.reason,
            last_seen_at=event.last_seen_at,
            detected_at=event.detected_at,
            downtime_seconds=event.downtime_seconds,
            created_at=event.created_at,
        )
