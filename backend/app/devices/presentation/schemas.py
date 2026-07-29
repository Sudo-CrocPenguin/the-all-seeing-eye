from datetime import datetime

from pydantic import BaseModel, Field

from backend.app.devices.application.provision_agent_credential import (
    ProvisionAgentCredentialCommand,
    ProvisionedAgentCredential,
)
from backend.app.devices.application.register_device import RegisterDeviceCommand
from backend.app.devices.domain.entities import Device


class RegisterDeviceRequest(BaseModel):
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    metadata: dict[str, str] = Field(default_factory=dict)

    def to_command(self) -> RegisterDeviceCommand:
        return RegisterDeviceCommand(
            device_id=self.device_id,
            hostname=self.hostname,
            os_name=self.os_name,
            agent_version=self.agent_version,
            metadata=self.metadata,
        )


class ProvisionAgentCredentialRequest(BaseModel):
    device_id: str

    def to_command(self) -> ProvisionAgentCredentialCommand:
        return ProvisionAgentCredentialCommand(device_id=self.device_id)


class ProvisionAgentCredentialResponse(BaseModel):
    device_id: str
    token: str
    created_at: datetime

    @classmethod
    def from_result(
        cls,
        result: ProvisionedAgentCredential,
    ) -> "ProvisionAgentCredentialResponse":
        return cls(
            device_id=result.device_id,
            token=result.token,
            created_at=result.created_at,
        )


class DeviceResponse(BaseModel):
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    registered_at: datetime
    last_seen_at: datetime | None
    metadata: dict[str, str]

    @classmethod
    def from_domain(cls, device: Device) -> "DeviceResponse":
        return cls(
            device_id=device.device_id,
            hostname=device.hostname,
            os_name=device.os_name,
            agent_version=device.agent_version,
            registered_at=device.registered_at,
            last_seen_at=device.last_seen_at,
            metadata=device.metadata,
        )
