from dataclasses import dataclass

from backend.app.devices.application.token_hasher import AgentTokenHasher
from backend.app.devices.domain.credential_repository import AgentCredentialRepository


@dataclass(frozen=True, slots=True)
class AuthenticateAgentCommand:
    device_id: str
    token: str


class AuthenticateAgentUseCase:
    def __init__(
        self,
        repository: AgentCredentialRepository,
        token_hasher: AgentTokenHasher | None = None,
    ) -> None:
        self._repository = repository
        self._token_hasher = token_hasher or AgentTokenHasher()

    def execute(self, command: AuthenticateAgentCommand) -> bool:
        credential = self._repository.find_by_device_id(command.device_id)
        if credential is None or not credential.is_active:
            return False

        is_valid = self._token_hasher.verify(
            command.token,
            expected_hash=credential.token_hash,
            token_salt=credential.token_salt,
        )
        if is_valid:
            credential.mark_used()
            self._repository.save(credential)
        return is_valid

