from secrets import compare_digest

from fastapi import HTTPException, Request, status

from backend.app.companies.domain.entities import AuditorSession
from backend.app.devices.application.authenticate_agent import (
    AuthenticateAgentCommand,
    AuthenticateAgentUseCase,
)
from backend.app.devices.domain.entities import Device
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


def require_auditor_token(request: Request, settings: Settings) -> None:
    if not settings.auditor_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Las consultas de auditoria no estan habilitadas",
        )

    supplied_token = request.headers.get(settings.auditor_token_header)
    if supplied_token is None or not compare_digest(supplied_token, settings.auditor_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de auditoria invalido",
        )


def require_auditor_session(
    request: Request,
    settings: Settings,
    container: AppContainer,
    *,
    company_id: str | None = None,
    required_scope: str | None = None,
) -> AuditorSession:
    session_id = request.headers.get(settings.auditor_session_header)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion de auditor requerida",
        )

    session = container.auditor_session_repository.find_by_id(session_id)
    if session is None or not session.is_active():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion de auditor invalida",
        )
    if company_id is not None and session.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion de auditor invalida",
        )
    if required_scope is not None and required_scope not in session.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La sesion de auditor no tiene permisos suficientes",
        )
    return session


def require_agent_token(
    request: Request,
    settings: Settings,
    container: AppContainer,
    *,
    device_id: str,
    require_registered_device: bool = False,
) -> Device | None:
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

    if not require_registered_device:
        return None

    device = container.device_repository.find_by_id(device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dispositivo no registrado",
        )
    return device
