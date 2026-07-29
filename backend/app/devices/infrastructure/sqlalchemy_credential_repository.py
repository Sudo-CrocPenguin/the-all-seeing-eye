from sqlalchemy.orm import Session

from backend.app.devices.domain.credential_repository import AgentCredentialRepository
from backend.app.devices.domain.credentials import AgentCredential
from backend.app.devices.infrastructure.sqlalchemy_models import AgentCredentialModel


def _model_to_domain(model: AgentCredentialModel) -> AgentCredential:
    return AgentCredential(
        device_id=model.device_id,
        token_hash=model.token_hash,
        token_salt=model.token_salt,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
        revoked_at=model.revoked_at,
    )


def _update_model(model: AgentCredentialModel, credential: AgentCredential) -> None:
    model.token_hash = credential.token_hash
    model.token_salt = credential.token_salt
    model.created_at = credential.created_at
    model.last_used_at = credential.last_used_at
    model.revoked_at = credential.revoked_at


class SQLAlchemyAgentCredentialRepository(AgentCredentialRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, credential: AgentCredential) -> AgentCredential:
        model = self._session.get(AgentCredentialModel, credential.device_id)
        if model is None:
            model = AgentCredentialModel(
                device_id=credential.device_id,
                token_hash=credential.token_hash,
                token_salt=credential.token_salt,
                created_at=credential.created_at,
                last_used_at=credential.last_used_at,
                revoked_at=credential.revoked_at,
            )
            self._session.add(model)
        else:
            _update_model(model, credential)

        self._session.flush()
        return _model_to_domain(model)

    def find_by_device_id(self, device_id: str) -> AgentCredential | None:
        model = self._session.get(AgentCredentialModel, device_id)
        if model is None:
            return None
        return _model_to_domain(model)
