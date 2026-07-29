from dataclasses import dataclass, field

from backend.app.devices.domain.entities import Device
from backend.app.devices.domain.repositories import DeviceRepository
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class RegisterDeviceCommand:
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    metadata: dict[str, str] = field(default_factory=dict)


class RegisterDeviceUseCase:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def execute(self, command: RegisterDeviceCommand) -> Device:
        existing = self._repository.find_by_id(command.device_id)
        if existing is not None:
            existing.hostname = command.hostname
            existing.os_name = command.os_name
            existing.agent_version = command.agent_version
            existing.metadata = command.metadata
            existing.mark_seen()
            return self._repository.save(existing)

        device = Device(
            device_id=command.device_id,
            hostname=command.hostname,
            os_name=command.os_name,
            agent_version=command.agent_version,
            registered_at=utc_now(),
            last_seen_at=utc_now(),
            metadata=command.metadata,
        )
        return self._repository.save(device)

