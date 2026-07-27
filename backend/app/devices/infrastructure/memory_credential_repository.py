from threading import Lock

from backend.app.devices.domain.credential_repository import AgentCredentialRepository
from backend.app.devices.domain.credentials import AgentCredential


class InMemoryAgentCredentialRepository(AgentCredentialRepository):
    def __init__(self) -> None:
        self._items: dict[str, AgentCredential] = {}
        self._lock = Lock()

    def save(self, credential: AgentCredential) -> AgentCredential:
        with self._lock:
            self._items[credential.device_id] = credential
        return credential

    def find_by_device_id(self, device_id: str) -> AgentCredential | None:
        with self._lock:
            return self._items.get(device_id)

