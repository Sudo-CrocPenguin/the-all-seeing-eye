from dataclasses import dataclass
from datetime import datetime

from backend.app.devices.application.token_hasher import AgentTokenHasher
from backend.app.devices.domain.credential_repository import AgentCredentialRepository
from backend.app.devices.domain.credentials import AgentCredential
from backend.app.shared.time import utc_now


@dataclass(frozen=True, slots=True)
class ProvisionAgentCredentialCommand:
    device_id: str


@dataclass(frozen=True, slots=True)
class ProvisionedAgentCredential:
    device_id: str
    token: str
    created_at: datetime


class ProvisionAgentCredentialUseCase:
    def __init__(
        self,
        repository: AgentCredentialRepository,
        token_hasher: AgentTokenHasher | None = None,
    ) -> None:
        self._repository = repository
        self._token_hasher = token_hasher or AgentTokenHasher()

    def execute(self, command: ProvisionAgentCredentialCommand) -> ProvisionedAgentCredential:
        raw_token = self._token_hasher.generate_token()
        hashed_token = self._token_hasher.hash_token(raw_token)
        credential = AgentCredential(
            device_id=command.device_id,
            token_hash=hashed_token.token_hash,
            token_salt=hashed_token.token_salt,
            created_at=utc_now(),
        )
        saved_credential = self._repository.save(credential)
        return ProvisionedAgentCredential(
            device_id=saved_credential.device_id,
            token=raw_token,
            created_at=saved_credential.created_at,
        )
