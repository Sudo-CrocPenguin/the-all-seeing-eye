from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.devices.domain.entities import Device
from backend.app.devices.infrastructure.sqlalchemy_models import DeviceModel


def _model_to_domain(model: DeviceModel) -> Device:
    metadata = cast(dict[str, str], model.extra_metadata or {})
    return Device(
        device_id=model.device_id,
        hostname=model.hostname,
        os_name=model.os_name,
        agent_version=model.agent_version,
        registered_at=model.registered_at,
        last_seen_at=model.last_seen_at,
        metadata=dict(metadata),
    )


def _update_model(model: DeviceModel, device: Device) -> None:
    model.hostname = device.hostname
    model.os_name = device.os_name
    model.agent_version = device.agent_version
    model.registered_at = device.registered_at
    model.last_seen_at = device.last_seen_at
    model.extra_metadata = dict(device.metadata)


class SQLAlchemyDeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, device: Device) -> Device:
        model = self._session.get(DeviceModel, device.device_id)
        if model is None:
            model = DeviceModel(
                device_id=device.device_id,
                hostname=device.hostname,
                os_name=device.os_name,
                agent_version=device.agent_version,
                registered_at=device.registered_at,
                last_seen_at=device.last_seen_at,
                extra_metadata=dict(device.metadata),
            )
            self._session.add(model)
        else:
            _update_model(model, device)

        self._session.flush()
        return _model_to_domain(model)

    def find_by_id(self, device_id: str) -> Device | None:
        model = self._session.get(DeviceModel, device_id)
        if model is None:
            return None
        return _model_to_domain(model)

    def list_all(self) -> list[Device]:
        statement = select(DeviceModel).order_by(DeviceModel.registered_at.desc())
        models = self._session.scalars(statement).all()
        return [_model_to_domain(model) for model in models]

