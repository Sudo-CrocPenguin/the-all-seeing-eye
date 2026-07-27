from dataclasses import dataclass, field

from backend.app.audit.domain.repositories import (
    AgentLifecycleEventRepository,
    NetworkAuditEventRepository,
)
from backend.app.audit.infrastructure.memory_event_repository import (
    InMemoryAgentLifecycleEventRepository,
    InMemoryNetworkAuditEventRepository,
)
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.devices.infrastructure.memory_device_repository import InMemoryDeviceRepository


@dataclass(slots=True)
class AppContainer:
    device_repository: DeviceRepository = field(default_factory=InMemoryDeviceRepository)
    network_event_repository: NetworkAuditEventRepository = field(
        default_factory=InMemoryNetworkAuditEventRepository,
    )
    lifecycle_event_repository: AgentLifecycleEventRepository = field(
        default_factory=InMemoryAgentLifecycleEventRepository,
    )


def build_container() -> AppContainer:
    return AppContainer()

