from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.shared.container import RuntimeContainer

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health_check(request: Request) -> dict[str, str] | JSONResponse:
    runtime_container: RuntimeContainer = request.app.state.container
    if runtime_container.settings.persistence_backend == "memory":
        return {
            "status": "ok",
            "persistence": "memory",
            "database": "not_configured",
        }

    if runtime_container.engine is None:
        return _unhealthy_response("database_engine_missing")

    try:
        with runtime_container.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return _unhealthy_response("database_unavailable")

    return {
        "status": "ok",
        "persistence": "sqlalchemy",
        "database": "ok",
    }


def _unhealthy_response(reason: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "unhealthy",
            "persistence": "sqlalchemy",
            "database": reason,
        },
    )
