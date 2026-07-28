from datetime import datetime
from ipaddress import ip_address
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from backend.app.audit.application.detect_missed_heartbeats import (
    DetectMissedHeartbeatsCommand,
    DetectMissedHeartbeatsUseCase,
)
from backend.app.audit.application.ingest_lifecycle_event import (
    IngestAgentLifecycleEventUseCase,
)
from backend.app.audit.application.ingest_network_event import IngestNetworkAuditEventUseCase
from backend.app.audit.application.record_agent_activity import (
    RecordAgentActivityCommand,
    RecordAgentActivityUseCase,
)
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    NetworkAuditEventFilters,
)
from backend.app.audit.presentation.schemas import (
    AgentLifecycleEventRequest,
    AgentLifecycleEventResponse,
    AgentLifecycleEventTypeRequest,
    NetworkAuditEventRequest,
    NetworkAuditEventResponse,
)
from backend.app.shared.container import AppContainer
from backend.app.shared.dependencies import get_container
from backend.app.shared.security import (
    require_agent_token,
    require_auditor_token,
    require_provisioning_token,
)

router = APIRouter(prefix="/audit", tags=["audit"])

FromDateTimeQuery = Annotated[datetime | None, Query(alias="from")]
ToDateTimeQuery = Annotated[datetime | None, Query(alias="to")]
LimitQuery = Annotated[int, Query(ge=1, le=500)]

_LIFECYCLE_EVENTS_THAT_MARK_DEVICE_SEEN = {
    AgentLifecycleEventTypeRequest.STARTED,
    AgentLifecycleEventTypeRequest.STOPPING,
    AgentLifecycleEventTypeRequest.STOPPED,
    AgentLifecycleEventTypeRequest.HEARTBEAT,
    AgentLifecycleEventTypeRequest.RECOVERED,
    AgentLifecycleEventTypeRequest.CONFIG_CHANGED,
}

_LIFECYCLE_EVENTS_THAT_DETECT_RECOVERY = {
    AgentLifecycleEventTypeRequest.STARTED,
    AgentLifecycleEventTypeRequest.HEARTBEAT,
    AgentLifecycleEventTypeRequest.CONFIG_CHANGED,
}


def _observed_public_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    host = request.client.host
    try:
        ip_address(host)
    except ValueError:
        return None
    return host


def _record_agent_activity(
    container: AppContainer,
    command: RecordAgentActivityCommand,
) -> None:
    use_case = RecordAgentActivityUseCase(
        container.device_repository,
        container.lifecycle_event_repository,
    )
    use_case.execute(command)


@router.post(
    "/network-events",
    response_model=NetworkAuditEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_network_event(
    payload: NetworkAuditEventRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> NetworkAuditEventResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
    )
    observed_public_ip = _observed_public_ip(request)
    use_case = IngestNetworkAuditEventUseCase(container.network_event_repository)
    event = use_case.execute(payload.to_command(observed_public_ip))
    _record_agent_activity(
        container,
        RecordAgentActivityCommand(
            device_id=payload.device_id,
            hostname=payload.hostname,
            agent_version=payload.agent_version,
            local_ip=payload.local_ip,
            public_ip=payload.public_ip or observed_public_ip,
        ),
    )
    return NetworkAuditEventResponse.from_domain(event)


@router.get("/network-events", response_model=list[NetworkAuditEventResponse])
async def search_network_events(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    device_id: str | None = None,
    local_ip: str | None = None,
    public_ip: str | None = None,
    destination_host: str | None = None,
    destination_ip: str | None = None,
    protocol: str | None = None,
    from_datetime: FromDateTimeQuery = None,
    to_datetime: ToDateTimeQuery = None,
    limit: LimitQuery = 100,
) -> list[NetworkAuditEventResponse]:
    require_auditor_token(request, request.app.state.container.settings)
    filters = NetworkAuditEventFilters(
        device_id=device_id,
        local_ip=local_ip,
        public_ip=public_ip,
        destination_host=destination_host,
        destination_ip=destination_ip,
        protocol=protocol,
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        limit=limit,
    )
    events = container.network_event_repository.search(filters)
    return [NetworkAuditEventResponse.from_domain(event) for event in events]


@router.post(
    "/lifecycle-events",
    response_model=AgentLifecycleEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_lifecycle_event(
    payload: AgentLifecycleEventRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> AgentLifecycleEventResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
    )
    observed_public_ip = _observed_public_ip(request)
    if payload.event_type in _LIFECYCLE_EVENTS_THAT_MARK_DEVICE_SEEN:
        _record_agent_activity(
            container,
            RecordAgentActivityCommand(
                device_id=payload.device_id,
                hostname=payload.hostname,
                agent_version=payload.agent_version,
                local_ip=payload.local_ip,
                public_ip=payload.public_ip or observed_public_ip,
                detect_recovery=payload.event_type in _LIFECYCLE_EVENTS_THAT_DETECT_RECOVERY,
            ),
        )

    use_case = IngestAgentLifecycleEventUseCase(container.lifecycle_event_repository)
    event = use_case.execute(payload.to_command(observed_public_ip))
    return AgentLifecycleEventResponse.from_domain(event)


@router.post(
    "/lifecycle-events/detect-missed-heartbeats",
    response_model=list[AgentLifecycleEventResponse],
)
async def detect_missed_heartbeats(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> list[AgentLifecycleEventResponse]:
    require_provisioning_token(request, request.app.state.container.settings)
    use_case = DetectMissedHeartbeatsUseCase(
        container.device_repository,
        container.lifecycle_event_repository,
    )
    events = use_case.execute(
        DetectMissedHeartbeatsCommand(
            timeout_seconds=request.app.state.container.settings.agent_heartbeat_timeout_seconds,
        ),
    )
    return [AgentLifecycleEventResponse.from_domain(event) for event in events]


@router.get("/lifecycle-events", response_model=list[AgentLifecycleEventResponse])
async def search_lifecycle_events(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    device_id: str | None = None,
    event_type: str | None = None,
    from_datetime: FromDateTimeQuery = None,
    to_datetime: ToDateTimeQuery = None,
    limit: LimitQuery = 100,
) -> list[AgentLifecycleEventResponse]:
    require_auditor_token(request, request.app.state.container.settings)
    filters = AgentLifecycleEventFilters(
        device_id=device_id,
        event_type=event_type,
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        limit=limit,
    )
    events = container.lifecycle_event_repository.search(filters)
    return [AgentLifecycleEventResponse.from_domain(event) for event in events]
