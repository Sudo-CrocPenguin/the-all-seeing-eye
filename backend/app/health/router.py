from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection

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
            migration = _migration_status(connection)
    except Exception:
        return _unhealthy_response("database_unavailable")

    if runtime_container.settings.health_require_current_migration and migration != "ok":
        return _unhealthy_response(f"migration_{migration}")

    return {
        "status": "ok",
        "persistence": "sqlalchemy",
        "database": "ok",
        "migration": migration,
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


def _migration_status(connection: Connection) -> str:
    current_revision = MigrationContext.configure(connection).get_current_revision()
    if current_revision is None:
        return "not_configured"

    alembic_config = Config(str(_project_root() / "alembic.ini"))
    expected_revision = ScriptDirectory.from_config(alembic_config).get_current_head()
    if current_revision == expected_revision:
        return "ok"
    return "outdated"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]
