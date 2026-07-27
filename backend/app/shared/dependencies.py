from fastapi import Request

from backend.app.shared.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container

