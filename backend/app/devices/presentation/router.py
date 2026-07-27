from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from backend.app.devices.application.provision_agent_credential import (
    ProvisionAgentCredentialUseCase,
)
from backend.app.devices.application.register_device import RegisterDeviceUseCase
from backend.app.devices.presentation.schemas import (
    DeviceResponse,
    ProvisionAgentCredentialRequest,
    ProvisionAgentCredentialResponse,
    RegisterDeviceRequest,
)
from backend.app.shared.container import AppContainer
from backend.app.shared.dependencies import get_container
from backend.app.shared.security import require_agent_token, require_provisioning_token

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post(
    "/agent-credentials",
    response_model=ProvisionAgentCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_agent_credential(
    payload: ProvisionAgentCredentialRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> ProvisionAgentCredentialResponse:
    require_provisioning_token(request, request.app.state.container.settings)
    use_case = ProvisionAgentCredentialUseCase(container.agent_credential_repository)
    credential = use_case.execute(payload.to_command())
    return ProvisionAgentCredentialResponse.from_result(credential)


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: RegisterDeviceRequest,
    request: Request,
    container: Annotated[AppContainer, Depends(get_container)],
) -> DeviceResponse:
    require_agent_token(
        request,
        request.app.state.container.settings,
        container,
        device_id=payload.device_id,
    )
    use_case = RegisterDeviceUseCase(container.device_repository)
    device = use_case.execute(payload.to_command())
    return DeviceResponse.from_domain(device)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    container: Annotated[AppContainer, Depends(get_container)],
) -> list[DeviceResponse]:
    return [DeviceResponse.from_domain(device) for device in container.device_repository.list_all()]
