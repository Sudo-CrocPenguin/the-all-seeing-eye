from datetime import datetime
from ipaddress import ip_address
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from backend.app.audit.application.ingest_lifecycle_event import (
    IngestAgentLifecycleEventUseCase,
)
from backend.app.audit.application.ingest_network_event import IngestNetworkAuditEventUseCase
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    NetworkAuditEventFilters,
)
from backend.app.audit.presentation.schemas import (
    AgentLifecycleEventRequest,
    AgentLifecycleEventResponse,
    NetworkAuditEventRequest,
    NetworkAuditEventResponse,
)
from backend.app.shared.container import AppContainer
from backend.app.shared.dependencies import get_container

router = APIRouter(prefix="/audit", tags=["audit"])


def _observed_public_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    host = request.client.host
    try:
        ip_address(host)
    except ValueError:
        return None
    return host


@router.post(
    "/network-events",
    response_model=NetworkAuditEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_network_event(
    payload: NetworkAuditEventRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> NetworkAuditEventResponse:
    use_case = IngestNetworkAuditEventUseCase(container.network_event_repository)
    event = use_case.execute(payload.to_command(_observed_public_ip(request)))
    return NetworkAuditEventResponse.from_domain(event)


@router.get("/network-events", response_model=list[NetworkAuditEventResponse])
def search_network_events(
    container: Annotated[AppContainer, Depends(get_container)],
    device_id: str | None = None,
    local_ip: str | None = None,
    public_ip: str | None = None,
    destination_host: str | None = None,
    destination_ip: str | None = None,
    protocol: str | None = None,
    from_datetime: datetime | None = Query(default=None, alias="from"),
    to_datetime: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[NetworkAuditEventResponse]:
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
def ingest_lifecycle_event(
    payload: AgentLifecycleEventRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> AgentLifecycleEventResponse:
    use_case = IngestAgentLifecycleEventUseCase(container.lifecycle_event_repository)
    event = use_case.execute(payload.to_command(_observed_public_ip(request)))
    return AgentLifecycleEventResponse.from_domain(event)


@router.get("/lifecycle-events", response_model=list[AgentLifecycleEventResponse])
def search_lifecycle_events(
    container: Annotated[AppContainer, Depends(get_container)],
    device_id: str | None = None,
    event_type: str | None = None,
    from_datetime: datetime | None = Query(default=None, alias="from"),
    to_datetime: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AgentLifecycleEventResponse]:
    filters = AgentLifecycleEventFilters(
        device_id=device_id,
        event_type=event_type,
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        limit=limit,
    )
    events = container.lifecycle_event_repository.search(filters)
    return [AgentLifecycleEventResponse.from_domain(event) for event in events]

