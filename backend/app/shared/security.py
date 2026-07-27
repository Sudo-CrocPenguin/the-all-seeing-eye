from secrets import compare_digest

from fastapi import HTTPException, Request, status

from backend.app.devices.application.authenticate_agent import (
    AuthenticateAgentCommand,
    AuthenticateAgentUseCase,
)
from backend.app.shared.config import Settings
from backend.app.shared.container import AppContainer


def require_provisioning_token(request: Request, settings: Settings) -> None:
    if not settings.provisioning_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La provision de agentes no esta habilitada",
        )

    supplied_token = request.headers.get(settings.provisioning_token_header)
    if supplied_token is None or not compare_digest(supplied_token, settings.provisioning_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de provision invalido",
        )


def require_agent_token(
    request: Request,
    settings: Settings,
    container: AppContainer,
    *,
    device_id: str,
) -> None:
    supplied_token = request.headers.get(settings.agent_token_header)
    if not supplied_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente requerido",
        )

    use_case = AuthenticateAgentUseCase(container.agent_credential_repository)
    is_authenticated = use_case.execute(
        AuthenticateAgentCommand(device_id=device_id, token=supplied_token),
    )
    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de agente invalido",
        )
