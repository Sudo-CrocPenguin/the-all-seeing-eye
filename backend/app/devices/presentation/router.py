from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.app.devices.application.register_device import RegisterDeviceUseCase
from backend.app.devices.presentation.schemas import DeviceResponse, RegisterDeviceRequest
from backend.app.shared.container import AppContainer
from backend.app.shared.dependencies import get_container

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: RegisterDeviceRequest,
    container: Annotated[AppContainer, Depends(get_container)],
) -> DeviceResponse:
    use_case = RegisterDeviceUseCase(container.device_repository)
    device = use_case.execute(payload.to_command())
    return DeviceResponse.from_domain(device)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    container: Annotated[AppContainer, Depends(get_container)],
) -> list[DeviceResponse]:
    return [DeviceResponse.from_domain(device) for device in container.device_repository.list_all()]
