from dataclasses import dataclass
from datetime import datetime

from backend.app.devices.domain.entities import Device
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class MarkDeviceSeenCommand:
    device_id: str
    seen_at: datetime | None = None


class MarkDeviceSeenUseCase:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def execute(self, command: MarkDeviceSeenCommand) -> Device | None:
        device = self._repository.find_by_id(command.device_id)
        if device is None:
            return None

        device.mark_seen(command.seen_at or utc_now())
        return self._repository.save(device)
