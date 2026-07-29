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
from backend.app.companies.domain.repositories import (
    AuditorAccessRequestRepository,
    AuditorSessionRepository,
    CompanyDeviceLinkRepository,
    CompanyRepository,
    EnrollmentCodeRepository,
    EnrollmentRequestRepository,
)
from backend.app.companies.infrastructure.memory_repositories import (
    InMemoryAuditorAccessRequestRepository,
    InMemoryAuditorSessionRepository,
    InMemoryCompanyDeviceLinkRepository,
    InMemoryCompanyRepository,
    InMemoryEnrollmentCodeRepository,
    InMemoryEnrollmentRequestRepository,
)
from backend.app.companies.infrastructure.sqlalchemy_repositories import (
    SQLAlchemyAuditorAccessRequestRepository,
    SQLAlchemyAuditorSessionRepository,
    SQLAlchemyCompanyDeviceLinkRepository,
    SQLAlchemyCompanyRepository,
    SQLAlchemyEnrollmentCodeRepository,
    SQLAlchemyEnrollmentRequestRepository,
)
from backend.app.devices.domain.credential_repository import AgentCredentialRepository
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.devices.infrastructure.memory_credential_repository import (
    InMemoryAgentCredentialRepository,
)
from backend.app.devices.infrastructure.memory_device_repository import InMemoryDeviceRepository
from backend.app.devices.infrastructure.sqlalchemy_credential_repository import (
    SQLAlchemyAgentCredentialRepository,
)
from backend.app.devices.infrastructure.sqlalchemy_device_repository import (
    SQLAlchemyDeviceRepository,
)
from backend.app.shared.config import Settings, get_settings
from backend.app.shared.database import build_engine, create_database_schema


@dataclass(slots=True)
class AppContainer:
    device_repository: DeviceRepository = field(default_factory=InMemoryDeviceRepository)
    agent_credential_repository: AgentCredentialRepository = field(
        default_factory=InMemoryAgentCredentialRepository,
    )
    network_event_repository: NetworkAuditEventRepository = field(
        default_factory=InMemoryNetworkAuditEventRepository,
    )
    lifecycle_event_repository: AgentLifecycleEventRepository = field(
        default_factory=InMemoryAgentLifecycleEventRepository,
    )
    company_repository: CompanyRepository = field(default_factory=InMemoryCompanyRepository)
    enrollment_code_repository: EnrollmentCodeRepository = field(
        default_factory=InMemoryEnrollmentCodeRepository,
    )
    enrollment_request_repository: EnrollmentRequestRepository = field(
        default_factory=InMemoryEnrollmentRequestRepository,
    )
    company_device_link_repository: CompanyDeviceLinkRepository = field(
        default_factory=InMemoryCompanyDeviceLinkRepository,
    )
    auditor_access_request_repository: AuditorAccessRequestRepository = field(
        default_factory=InMemoryAuditorAccessRequestRepository,
    )
    auditor_session_repository: AuditorSessionRepository = field(
        default_factory=InMemoryAuditorSessionRepository,
    )


@dataclass(slots=True)
class RuntimeContainer:
    settings: Settings
    engine: Engine | None = None
    session_factory: sessionmaker[Session] | None = None
    memory_device_repository: InMemoryDeviceRepository = field(
        default_factory=InMemoryDeviceRepository,
    )
    memory_agent_credential_repository: InMemoryAgentCredentialRepository = field(
        default_factory=InMemoryAgentCredentialRepository,
    )
    memory_network_event_repository: InMemoryNetworkAuditEventRepository = field(
        default_factory=InMemoryNetworkAuditEventRepository,
    )
    memory_lifecycle_event_repository: InMemoryAgentLifecycleEventRepository = field(
        default_factory=InMemoryAgentLifecycleEventRepository,
    )
    memory_company_repository: InMemoryCompanyRepository = field(
        default_factory=InMemoryCompanyRepository,
    )
    memory_enrollment_code_repository: InMemoryEnrollmentCodeRepository = field(
        default_factory=InMemoryEnrollmentCodeRepository,
    )
    memory_enrollment_request_repository: InMemoryEnrollmentRequestRepository = field(
        default_factory=InMemoryEnrollmentRequestRepository,
    )
    memory_company_device_link_repository: InMemoryCompanyDeviceLinkRepository = field(
        default_factory=InMemoryCompanyDeviceLinkRepository,
    )
    memory_auditor_access_request_repository: InMemoryAuditorAccessRequestRepository = field(
        default_factory=InMemoryAuditorAccessRequestRepository,
    )
    memory_auditor_session_repository: InMemoryAuditorSessionRepository = field(
        default_factory=InMemoryAuditorSessionRepository,
    )

    def build_memory_container(self) -> AppContainer:
        return AppContainer(
            device_repository=self.memory_device_repository,
            agent_credential_repository=self.memory_agent_credential_repository,
            network_event_repository=self.memory_network_event_repository,
            lifecycle_event_repository=self.memory_lifecycle_event_repository,
            company_repository=self.memory_company_repository,
            enrollment_code_repository=self.memory_enrollment_code_repository,
            enrollment_request_repository=self.memory_enrollment_request_repository,
            company_device_link_repository=self.memory_company_device_link_repository,
            auditor_access_request_repository=self.memory_auditor_access_request_repository,
            auditor_session_repository=self.memory_auditor_session_repository,
        )

    def build_sqlalchemy_container(self, session: Session) -> AppContainer:
        return AppContainer(
            device_repository=SQLAlchemyDeviceRepository(session),
            agent_credential_repository=SQLAlchemyAgentCredentialRepository(session),
            network_event_repository=SQLAlchemyNetworkAuditEventRepository(session),
            lifecycle_event_repository=SQLAlchemyAgentLifecycleEventRepository(session),
            company_repository=SQLAlchemyCompanyRepository(session),
            enrollment_code_repository=SQLAlchemyEnrollmentCodeRepository(session),
            enrollment_request_repository=SQLAlchemyEnrollmentRequestRepository(session),
            company_device_link_repository=SQLAlchemyCompanyDeviceLinkRepository(session),
            auditor_access_request_repository=SQLAlchemyAuditorAccessRequestRepository(session),
            auditor_session_repository=SQLAlchemyAuditorSessionRepository(session),
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
