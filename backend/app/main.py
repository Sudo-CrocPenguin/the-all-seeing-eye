from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.audit.presentation.router import router as audit_router
from backend.app.devices.presentation.router import router as devices_router
from backend.app.health.router import router as health_router
from backend.app.shared.config import get_settings
from backend.app.shared.container import build_container
from backend.app.shared.domain import DomainValidationError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.state.container = build_container()

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(
        _request: Request,
        exc: DomainValidationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(health_router)
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    return app


app = create_app()

