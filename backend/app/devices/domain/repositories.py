from typing import Protocol

from backend.app.devices.domain.entities import Device


class DeviceRepository(Protocol):
    def save(self, device: Device) -> Device:
        raise NotImplementedError

    def find_by_id(self, device_id: str) -> Device | None:
        raise NotImplementedError

    def list_all(self) -> list[Device]:
        raise NotImplementedError

