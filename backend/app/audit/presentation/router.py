from dataclasses import replace
from datetime import datetime, timedelta
from ipaddress import ip_address, ip_network
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.app.audit.application.detect_missed_heartbeats import (
    DetectMissedHeartbeatsCommand,
    DetectMissedHeartbeatsUseCase,
)
from backend.app.audit.application.ingest_lifecycle_event import (
    IngestAgentLifecycleEventUseCase,
)
from backend.app.audit.application.ingest_network_event import IngestNetworkAuditEventUseCase
from backend.app.audit.application.query_device_movements import (
    QueryDeviceMovementsCommand,
    QueryDeviceMovementsUseCase,
)
from backend.app.audit.application.query_incident_window import (
    QueryIncidentWindowCommand,
    QueryIncidentWindowUseCase,
)
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
    DeviceMovementResponse,
    IncidentWindowResponse,
    NetworkAuditEventRequest,
    NetworkAuditEventResponse,
)
from backend.app.shared.config import Settings
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
IncidentAtQuery = Annotated[datetime | None, Query(alias="at")]
WindowSecondsQuery = Annotated[int, Query(ge=60, le=86_400)]
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

_PUBLIC_IP_HEADERS = (
    "X-Forwarded-For",
    "X-Real-IP",
    "CF-Connecting-IP",
)


def _observed_public_ip(request: Request, settings: Settings) -> str | None:
    if request.client is None:
        return None

    if _is_trusted_proxy(request.client.host, settings.trusted_proxy_ips):
        for header_name in _PUBLIC_IP_HEADERS:
            public_ip = _first_public_ip(request.headers.get(header_name))
            if public_ip is not None:
                return public_ip

    return _public_ip_or_none(request.client.host)


def _first_public_ip(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None

    for candidate in raw_value.split(","):
        public_ip = _public_ip_or_none(candidate)
        if public_ip is not None:
            return public_ip

    return None


def _public_ip_or_none(raw_value: str) -> str | None:
    try:
        parsed_ip = ip_address(raw_value.strip())
    except ValueError:
        return None
    if not parsed_ip.is_global:
        return None
    return str(parsed_ip)


def _is_trusted_proxy(client_host: str, trusted_proxy_ips: str) -> bool:
    trusted_ranges = [
        raw_range.strip()
        for raw_range in trusted_proxy_ips.split(",")
        if raw_range.strip()
    ]
    if not trusted_ranges:
        return False

    try:
        client_ip = ip_address(client_host)
    except ValueError:
        return False

    for raw_range in trusted_ranges:
        try:
            if client_ip in ip_network(raw_range, strict=False):
                return True
        except ValueError:
            continue

    return False


def _record_agent_activity(
    container: AppContainer,
    command: RecordAgentActivityCommand,
) -> None:
    use_case = RecordAgentActivityUseCase(
        container.device_repository,
        container.lifecycle_event_repository,
    )
    use_case.execute(command)


def _resolve_incident_window(
    *,
    from_datetime: datetime | None,
    to_datetime: datetime | None,
    incident_at: datetime | None,
    window_seconds: int,
) -> tuple[datetime, datetime]:
    if incident_at is not None:
        if from_datetime is not None or to_datetime is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use at o from/to, no ambos",
            )
        before_seconds = window_seconds // 2
        after_seconds = window_seconds - before_seconds
        return (
            incident_at - timedelta(seconds=before_seconds),
            incident_at + timedelta(seconds=after_seconds),
        )

    if from_datetime is None or to_datetime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe enviar from/to o at",
        )

    return from_datetime, to_datetime


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
    registered_device = require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    if registered_device is None:
        raise RuntimeError("El dispositivo registrado es obligatorio para eventos de red")
    observed_public_ip = _observed_public_ip(request, request.app.state.container.settings)
    use_case = IngestNetworkAuditEventUseCase(container.network_event_repository)
    command = replace(
        payload.to_command(observed_public_ip),
        hostname=registered_device.hostname,
        os_name=registered_device.os_name,
        agent_version=registered_device.agent_version,
    )
    event = use_case.execute(command)
    _record_agent_activity(
        container,
        RecordAgentActivityCommand(
            device_id=payload.device_id,
            hostname=registered_device.hostname,
            agent_version=registered_device.agent_version,
            local_ip=payload.local_ip,
            public_ip=observed_public_ip,
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


@router.get("/device-movements", response_model=list[DeviceMovementResponse])
async def search_device_movements(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    device_id: str,
    from_datetime: FromDateTimeQuery = None,
    to_datetime: ToDateTimeQuery = None,
    limit: LimitQuery = 100,
) -> list[DeviceMovementResponse]:
    require_auditor_token(request, request.app.state.container.settings)
    use_case = QueryDeviceMovementsUseCase(
        container.network_event_repository,
        container.lifecycle_event_repository,
    )
    movements = use_case.execute(
        QueryDeviceMovementsCommand(
            device_id=device_id,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            limit=limit,
        ),
    )
    return [DeviceMovementResponse.from_result(movement) for movement in movements]


@router.get("/incident-window", response_model=IncidentWindowResponse)
async def query_incident_window(
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
    from_datetime: FromDateTimeQuery = None,
    to_datetime: ToDateTimeQuery = None,
    incident_at: IncidentAtQuery = None,
    window_seconds: WindowSecondsQuery = 900,
    limit: LimitQuery = 500,
) -> IncidentWindowResponse:
    require_auditor_token(request, request.app.state.container.settings)
    resolved_from_datetime, resolved_to_datetime = _resolve_incident_window(
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        incident_at=incident_at,
        window_seconds=window_seconds,
    )
    use_case = QueryIncidentWindowUseCase(
        container.device_repository,
        container.network_event_repository,
        container.lifecycle_event_repository,
    )
    result = use_case.execute(
        QueryIncidentWindowCommand(
            from_datetime=resolved_from_datetime,
            to_datetime=resolved_to_datetime,
            limit=limit,
        ),
    )
    return IncidentWindowResponse.from_result(result)


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
    registered_device = require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
        require_registered_device=True,
    )
    if registered_device is None:
        raise RuntimeError("El dispositivo registrado es obligatorio para lifecycle")
    observed_public_ip = _observed_public_ip(request, request.app.state.container.settings)
    if payload.event_type in _LIFECYCLE_EVENTS_THAT_MARK_DEVICE_SEEN:
        _record_agent_activity(
            container,
            RecordAgentActivityCommand(
                device_id=payload.device_id,
                hostname=registered_device.hostname,
                agent_version=registered_device.agent_version,
                local_ip=payload.local_ip,
                public_ip=observed_public_ip,
                detect_recovery=payload.event_type in _LIFECYCLE_EVENTS_THAT_DETECT_RECOVERY,
            ),
        )

    use_case = IngestAgentLifecycleEventUseCase(container.lifecycle_event_repository)
    command = replace(
        payload.to_command(observed_public_ip),
        hostname=registered_device.hostname,
        agent_version=registered_device.agent_version,
    )
    event = use_case.execute(command)
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
