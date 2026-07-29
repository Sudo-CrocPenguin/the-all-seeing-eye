import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.audit.application.heartbeat_scheduler import missed_heartbeat_scheduler_loop
from backend.app.audit.presentation.router import router as audit_router
from backend.app.companies.presentation.router import router as companies_router
from backend.app.devices.presentation.router import router as devices_router
from backend.app.health.router import router as health_router
from backend.app.shared.config import Settings, get_settings
from backend.app.shared.container import RuntimeContainer, build_container
from backend.app.shared.domain import DomainValidationError

API_VERSION = "1.0.0"


def create_app(
    *,
    settings: Settings | None = None,
    create_schema: bool = False,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    runtime_container = build_container(resolved_settings, create_schema=create_schema)
    app = FastAPI(
        title=resolved_settings.app_name,
        version=API_VERSION,
        docs_url="/docs" if _api_docs_enabled(resolved_settings) else None,
        redoc_url="/redoc" if _api_docs_enabled(resolved_settings) else None,
        openapi_url="/openapi.json" if _api_docs_enabled(resolved_settings) else None,
        lifespan=_build_lifespan(runtime_container),
    )
    app.state.container = runtime_container

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(
        _request: Request,
        exc: DomainValidationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(health_router)
    app.include_router(companies_router, prefix="/api/v1")
    app.include_router(devices_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    return app


def _api_docs_enabled(settings: Settings) -> bool:
    return settings.api_docs_enabled and settings.app_env.lower() in {
        "local",
        "test",
        "development",
    }


def _build_lifespan(
    runtime_container: RuntimeContainer,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        scheduler_task: asyncio.Task[None] | None = None
        if runtime_container.settings.missed_heartbeat_scheduler_enabled:
            scheduler_task = asyncio.create_task(
                missed_heartbeat_scheduler_loop(runtime_container),
            )

        try:
            yield
        finally:
            if scheduler_task is not None:
                scheduler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await scheduler_task

    return lifespan


app = create_app()
