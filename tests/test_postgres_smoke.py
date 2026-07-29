import os

import httpx
import pytest

from backend.app.main import create_app
from backend.app.shared.config import Settings

PROVISIONING_TOKEN = "postgres-smoke-provisioning-token"


@pytest.mark.anyio
async def test_postgres_smoke_health_and_company_creation() -> None:
    database_url = os.getenv("POSTGRES_SMOKE_DATABASE_URL")
    if not database_url:
        pytest.skip("POSTGRES_SMOKE_DATABASE_URL no configurado")

    app = create_app(
        settings=Settings(
            app_env="local",
            api_docs_enabled=False,
            health_require_current_migration=True,
            database_url=database_url,
            persistence_backend="sqlalchemy",
            auditor_token="postgres-smoke-auditor-token",
            provisioning_token=PROVISIONING_TOKEN,
        ),
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health_response = await client.get("/health")
        company_response = await client.post(
            "/api/v1/companies",
            json={"name": "Postgres Smoke", "phone_number": "+15550000000"},
        )

    assert health_response.status_code == 200
    assert health_response.json()["migration"] == "ok"
    assert company_response.status_code == 201
    assert company_response.json()["name"] == "Postgres Smoke"
