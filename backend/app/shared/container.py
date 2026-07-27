from dataclasses import dataclass, field

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.audit.domain.repositories import (
    AgentLifecycleEventRepository,
    NetworkAuditEventRepository,
)
from backend.app.audit.infrastructure.memory_event_repository import (
    InMemoryAgentLifecycleEventRepository,
    InMemoryNetworkAuditEventRepository,
)
from backend.app.audit.infrastructure.sqlalchemy_event_repository import (
    SQLAlchemyAgentLifecycleEventRepository,
    SQLAlchemyNetworkAuditEventRepository,
)
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.devices.infrastructure.memory_device_repository import InMemoryDeviceRepository
from backend.app.devices.infrastructure.sqlalchemy_device_repository import (
    SQLAlchemyDeviceRepository,
)
from backend.app.shared.config import Settings, get_settings
from backend.app.shared.database import build_engine, create_database_schema


@dataclass(slots=True)
class AppContainer:
    device_repository: DeviceRepository = field(default_factory=InMemoryDeviceRepository)
    network_event_repository: NetworkAuditEventRepository = field(
        default_factory=InMemoryNetworkAuditEventRepository,
    )
    lifecycle_event_repository: AgentLifecycleEventRepository = field(
        default_factory=InMemoryAgentLifecycleEventRepository,
    )


@dataclass(slots=True)
class RuntimeContainer:
    settings: Settings
    engine: Engine | None = None
    session_factory: sessionmaker[Session] | None = None
    memory_device_repository: InMemoryDeviceRepository = field(
        default_factory=InMemoryDeviceRepository,
    )
    memory_network_event_repository: InMemoryNetworkAuditEventRepository = field(
        default_factory=InMemoryNetworkAuditEventRepository,
    )
    memory_lifecycle_event_repository: InMemoryAgentLifecycleEventRepository = field(
        default_factory=InMemoryAgentLifecycleEventRepository,
    )

    def build_memory_container(self) -> AppContainer:
        return AppContainer(
            device_repository=self.memory_device_repository,
            network_event_repository=self.memory_network_event_repository,
            lifecycle_event_repository=self.memory_lifecycle_event_repository,
        )

    def build_sqlalchemy_container(self, session: Session) -> AppContainer:
        return AppContainer(
            device_repository=SQLAlchemyDeviceRepository(session),
            network_event_repository=SQLAlchemyNetworkAuditEventRepository(session),
            lifecycle_event_repository=SQLAlchemyAgentLifecycleEventRepository(session),
        )


def build_container(
    settings: Settings | None = None,
    *,
    create_schema: bool = False,
) -> RuntimeContainer:
    resolved_settings = settings or get_settings()
    if resolved_settings.persistence_backend == "memory":
        return RuntimeContainer(settings=resolved_settings)

    engine = build_engine(resolved_settings)
    if create_schema:
        create_database_schema(engine)

    return RuntimeContainer(
        settings=resolved_settings,
        engine=engine,
        session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False),
    )
