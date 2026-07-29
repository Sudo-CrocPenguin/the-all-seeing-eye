from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.audit.domain.entities import (
    AgentLifecycleEvent,
    AgentLifecycleEventType,
    NetworkAuditEvent,
)
from backend.app.audit.domain.repositories import (
    AgentLifecycleEventFilters,
    NetworkAuditEventFilters,
)
from backend.app.audit.infrastructure.sqlalchemy_models import (
    AgentLifecycleEventModel,
    NetworkAuditEventModel,
)
from backend.app.shared.time import ensure_aware


def _network_model_to_domain(model: NetworkAuditEventModel) -> NetworkAuditEvent:
    request_metadata = cast(dict[str, str], model.request_metadata or {})
    response_metadata = cast(dict[str, str], model.response_metadata or {})
    return NetworkAuditEvent(
        event_id=model.event_id,
        occurred_at=model.occurred_at,
        device_id=model.device_id,
        company_id=model.company_id,
        company_device_link_id=model.company_device_link_id,
        hostname=model.hostname,
        os_name=model.os_name,
        agent_version=model.agent_version,
        protocol=model.protocol,
        local_ip=model.local_ip,
        public_ip=model.public_ip,
        destination_host=model.destination_host,
        destination_ip=model.destination_ip,
        destination_port=model.destination_port,
        http_method=model.http_method,
        http_status_code=model.http_status_code,
        bytes_sent=model.bytes_sent,
        bytes_received=model.bytes_received,
        network_interface=model.network_interface,
        mac_address=model.mac_address,
        local_username=model.local_username,
        process_id=model.process_id,
        process_name=model.process_name,
        process_executable=model.process_executable,
        service_name=model.service_name,
        request_metadata=dict(request_metadata),
        response_metadata=dict(response_metadata),
        created_at=model.created_at,
    )


def _network_domain_to_model(event: NetworkAuditEvent) -> NetworkAuditEventModel:
    return NetworkAuditEventModel(
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        device_id=event.device_id,
        company_id=event.company_id,
        company_device_link_id=event.company_device_link_id,
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
        request_metadata=dict(event.request_metadata),
        response_metadata=dict(event.response_metadata),
        created_at=event.created_at,
    )


def _lifecycle_model_to_domain(model: AgentLifecycleEventModel) -> AgentLifecycleEvent:
    return AgentLifecycleEvent(
        event_id=model.event_id,
        event_type=AgentLifecycleEventType(model.event_type),
        occurred_at=model.occurred_at,
        device_id=model.device_id,
        company_id=model.company_id,
        company_device_link_id=model.company_device_link_id,
        hostname=model.hostname,
        agent_version=model.agent_version,
        local_ip=model.local_ip,
        public_ip=model.public_ip,
        reason=model.reason,
        last_seen_at=model.last_seen_at,
        detected_at=model.detected_at,
        downtime_seconds=model.downtime_seconds,
        created_at=model.created_at,
    )


def _lifecycle_domain_to_model(event: AgentLifecycleEvent) -> AgentLifecycleEventModel:
    return AgentLifecycleEventModel(
        event_id=event.event_id,
        event_type=event.event_type.value,
        occurred_at=event.occurred_at,
        device_id=event.device_id,
        company_id=event.company_id,
        company_device_link_id=event.company_device_link_id,
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


class SQLAlchemyNetworkAuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, event: NetworkAuditEvent) -> NetworkAuditEvent:
        model = _network_domain_to_model(event)
        self._session.add(model)
        self._session.flush()
        return _network_model_to_domain(model)

    def search(self, filters: NetworkAuditEventFilters) -> list[NetworkAuditEvent]:
        statement = select(NetworkAuditEventModel)
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(NetworkAuditEventModel.occurred_at.desc()).limit(
            max(filters.limit, 0),
        )
        models = self._session.scalars(statement).all()
        return [_network_model_to_domain(model) for model in models]

    def list_device_ids(self, filters: NetworkAuditEventFilters) -> set[str]:
        statement = select(NetworkAuditEventModel.device_id).distinct()
        statement = self._apply_filters(statement, filters)
        return set(self._session.scalars(statement).all())

    def latest_seen_at_by_device(self, filters: NetworkAuditEventFilters) -> dict[str, datetime]:
        statement = select(
            NetworkAuditEventModel.device_id,
            func.max(NetworkAuditEventModel.occurred_at),
        )
        statement = self._apply_filters(statement, filters)
        statement = statement.group_by(NetworkAuditEventModel.device_id)
        return {
            device_id: ensure_aware(latest_seen_at)
            for device_id, latest_seen_at in self._session.execute(statement).all()
            if latest_seen_at is not None
        }

    def _apply_filters(
        self,
        statement: Select[Any],
        filters: NetworkAuditEventFilters,
    ) -> Select[Any]:
        if filters.company_id:
            statement = statement.where(NetworkAuditEventModel.company_id == filters.company_id)
        if filters.company_device_link_id:
            statement = statement.where(
                NetworkAuditEventModel.company_device_link_id
                == filters.company_device_link_id,
            )
        if filters.device_id:
            statement = statement.where(NetworkAuditEventModel.device_id == filters.device_id)
        if filters.local_ip:
            statement = statement.where(NetworkAuditEventModel.local_ip == filters.local_ip)
        if filters.public_ip:
            statement = statement.where(NetworkAuditEventModel.public_ip == filters.public_ip)
        if filters.destination_host:
            statement = statement.where(
                NetworkAuditEventModel.destination_host == filters.destination_host,
            )
        if filters.destination_ip:
            statement = statement.where(
                NetworkAuditEventModel.destination_ip == filters.destination_ip,
            )
        if filters.protocol:
            statement = statement.where(NetworkAuditEventModel.protocol == filters.protocol.upper())
        if filters.from_datetime:
            statement = statement.where(
                NetworkAuditEventModel.occurred_at >= ensure_aware(filters.from_datetime),
            )
        if filters.to_datetime:
            statement = statement.where(
                NetworkAuditEventModel.occurred_at <= ensure_aware(filters.to_datetime),
            )
        return statement


class SQLAlchemyAgentLifecycleEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, event: AgentLifecycleEvent) -> AgentLifecycleEvent:
        model = _lifecycle_domain_to_model(event)
        self._session.add(model)
        self._session.flush()
        return _lifecycle_model_to_domain(model)

    def search(self, filters: AgentLifecycleEventFilters) -> list[AgentLifecycleEvent]:
        statement = select(AgentLifecycleEventModel)
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(AgentLifecycleEventModel.occurred_at.desc()).limit(
            max(filters.limit, 0),
        )
        models = self._session.scalars(statement).all()
        return [_lifecycle_model_to_domain(model) for model in models]

    def list_device_ids(self, filters: AgentLifecycleEventFilters) -> set[str]:
        statement = select(AgentLifecycleEventModel.device_id).distinct()
        statement = self._apply_filters(statement, filters)
        return set(self._session.scalars(statement).all())

    def latest_seen_at_by_device(
        self,
        filters: AgentLifecycleEventFilters,
    ) -> dict[str, datetime]:
        statement = select(
            AgentLifecycleEventModel.device_id,
            func.max(AgentLifecycleEventModel.occurred_at),
        )
        statement = self._apply_filters(statement, filters)
        statement = statement.group_by(AgentLifecycleEventModel.device_id)
        return {
            device_id: ensure_aware(latest_seen_at)
            for device_id, latest_seen_at in self._session.execute(statement).all()
            if latest_seen_at is not None
        }

    def _apply_filters(
        self,
        statement: Select[Any],
        filters: AgentLifecycleEventFilters,
    ) -> Select[Any]:
        if filters.company_id:
            statement = statement.where(AgentLifecycleEventModel.company_id == filters.company_id)
        if filters.company_device_link_id:
            statement = statement.where(
                AgentLifecycleEventModel.company_device_link_id
                == filters.company_device_link_id,
            )
        if filters.device_id:
            statement = statement.where(AgentLifecycleEventModel.device_id == filters.device_id)
        if filters.event_type:
            statement = statement.where(AgentLifecycleEventModel.event_type == filters.event_type)
        if filters.from_datetime:
            statement = statement.where(
                AgentLifecycleEventModel.occurred_at >= ensure_aware(filters.from_datetime),
            )
        if filters.to_datetime:
            statement = statement.where(
                AgentLifecycleEventModel.occurred_at <= ensure_aware(filters.to_datetime),
            )
        return statement
