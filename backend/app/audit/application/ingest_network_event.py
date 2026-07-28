from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from backend.app.audit.domain.entities import NetworkAuditEvent
from backend.app.audit.domain.repositories import NetworkAuditEventRepository


@dataclass(frozen=True, slots=True)
class IngestNetworkAuditEventCommand:
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
    request_metadata: dict[str, str] = field(default_factory=dict)
    response_metadata: dict[str, str] = field(default_factory=dict)


class IngestNetworkAuditEventUseCase:
    def __init__(self, repository: NetworkAuditEventRepository) -> None:
        self._repository = repository

    def execute(self, command: IngestNetworkAuditEventCommand) -> NetworkAuditEvent:
        event = NetworkAuditEvent(
            event_id=str(uuid4()),
            occurred_at=command.occurred_at,
            device_id=command.device_id,
            hostname=command.hostname,
            os_name=command.os_name,
            agent_version=command.agent_version,
            protocol=command.protocol,
            local_ip=command.local_ip,
            public_ip=command.public_ip,
            destination_host=command.destination_host,
            destination_ip=command.destination_ip,
            destination_port=command.destination_port,
            http_method=command.http_method,
            http_status_code=command.http_status_code,
            bytes_sent=command.bytes_sent,
            bytes_received=command.bytes_received,
            network_interface=command.network_interface,
            mac_address=command.mac_address,
            local_username=command.local_username,
            process_id=command.process_id,
            process_name=command.process_name,
            process_executable=command.process_executable,
            service_name=command.service_name,
            request_metadata=command.request_metadata,
            response_metadata=command.response_metadata,
        )
        return self._repository.save(event)
