from fastapi import Request

from backend.app.shared.container import AppContainer


async def get_container(request: Request) -> AppContainer:
    return request.app.state.container
