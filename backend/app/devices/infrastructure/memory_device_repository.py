from threading import Lock

from backend.app.devices.domain.entities import Device


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self._items: dict[str, Device] = {}
        self._lock = Lock()

    def save(self, device: Device) -> Device:
        with self._lock:
            self._items[device.device_id] = device
        return device

    def find_by_id(self, device_id: str) -> Device | None:
        with self._lock:
            return self._items.get(device_id)

    def list_all(self) -> list[Device]:
        with self._lock:
            return list(self._items.values())

