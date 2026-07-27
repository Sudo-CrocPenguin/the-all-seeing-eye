from typing import Protocol

from backend.app.devices.domain.credentials import AgentCredential


class AgentCredentialRepository(Protocol):
    def save(self, credential: AgentCredential) -> AgentCredential:
        raise NotImplementedError

    def find_by_device_id(self, device_id: str) -> AgentCredential | None:
        raise NotImplementedError

