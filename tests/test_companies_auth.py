from datetime import UTC, datetime
from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from backend.app.companies.infrastructure.sqlalchemy_models import (
    CompanyDeviceLinkModel,
    EnrollmentRequestModel,
)
from backend.app.main import create_app
from backend.app.shared.config import Settings
from backend.app.shared.container import RuntimeContainer

PROVISIONING_TOKEN = "test-provisioning-token"


def create_test_app() -> FastAPI:
    return create_app(
        settings=Settings(
            app_env="local",
            database_url="sqlite+pysqlite:///:memory:",
            persistence_backend="sqlalchemy",
            auditor_token="test-auditor-token",
            provisioning_token=PROVISIONING_TOKEN,
        ),
        create_schema=True,
    )


def get_runtime_container(app: FastAPI) -> RuntimeContainer:
    return cast(RuntimeContainer, app.state.container)


async def provision_agent_token(
    client: httpx.AsyncClient,
    *,
    device_id: str,
) -> str:
    response = await client.post(
        "/api/v1/devices/agent-credentials",
        headers={"X-Provisioning-Token": PROVISIONING_TOKEN},
        json={"device_id": device_id},
    )
    assert response.status_code == 201
    token = response.json()["token"]
    assert isinstance(token, str)
    return token


async def register_device(
    client: httpx.AsyncClient,
    *,
    device_id: str,
    agent_token: str,
    hostname: str,
) -> None:
    response = await client.post(
        "/api/v1/devices",
        headers={"X-Agent-Token": agent_token},
        json={
            "device_id": device_id,
            "hostname": hostname,
            "os_name": "linux",
            "agent_version": "0.1.0-beta.1",
            "metadata": {"interfaces": "[]"},
        },
    )
    assert response.status_code == 201


async def create_company(client: httpx.AsyncClient) -> str:
    response = await client.post(
        "/api/v1/companies",
        json={"name": "Acme Auditoria", "phone_number": "+573001112233"},
    )
    assert response.status_code == 201
    company_id = response.json()["company_id"]
    assert isinstance(company_id, str)
    return company_id


async def create_auditor_session(
    client: httpx.AsyncClient,
    *,
    company_id: str,
    device_id: str,
    agent_token: str,
) -> str:
    access_response = await client.post(
        f"/api/v1/companies/{company_id}/auditor-access-requests",
        headers={"X-Agent-Token": agent_token},
        json={"device_id": device_id},
    )
    assert access_response.status_code == 201
    access_body = access_response.json()
    assert access_body["delivery_channel"] == "local_response"
    verification_code = access_body["verification_code"]
    assert isinstance(verification_code, str)
    assert len(verification_code) == 6

    verify_response = await client.post(
        (
            f"/api/v1/companies/{company_id}/auditor-access-requests/"
            f"{access_body['auditor_access_request_id']}/verify"
        ),
        headers={"X-Agent-Token": agent_token},
        json={"device_id": device_id, "verification_code": verification_code},
    )
    assert verify_response.status_code == 201
    session_body = verify_response.json()
    assert session_body["company_id"] == company_id
    assert session_body["device_id"] == device_id
    assert "devices:approve" in session_body["scopes"]
    assert datetime.fromisoformat(session_body["expires_at"]) > datetime.fromisoformat(
        session_body["created_at"],
    )
    session_id = session_body["auditor_session_id"]
    assert isinstance(session_id, str)
    return session_id


@pytest.mark.anyio
async def test_company_auditor_session_and_device_enrollment_flow() -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        company_id = await create_company(client)
        auditor_token = await provision_agent_token(client, device_id="device-auditor")
        await register_device(
            client,
            device_id="device-auditor",
            agent_token=auditor_token,
            hostname="AUDITOR-LAPTOP",
        )
        auditor_session_id = await create_auditor_session(
            client,
            company_id=company_id,
            device_id="device-auditor",
            agent_token=auditor_token,
        )

        code_response = await client.post(
            f"/api/v1/companies/{company_id}/enrollment-codes",
            headers={"X-Auditor-Session": auditor_session_id},
            json={"ttl_seconds": 3600, "max_uses": 1},
        )
        assert code_response.status_code == 201
        enrollment_code = code_response.json()["code"]
        assert isinstance(enrollment_code, str)

        device_token = await provision_agent_token(client, device_id="device-worker")
        await register_device(
            client,
            device_id="device-worker",
            agent_token=device_token,
            hostname="WORKER-LAPTOP",
        )

        request_response = await client.post(
            "/api/v1/companies/enrollment-requests",
            headers={"X-Agent-Token": device_token},
            json={
                "device_id": "device-worker",
                "enrollment_code": enrollment_code,
                "device_fingerprint_snapshot": {
                    "hostname": "WORKER-LAPTOP",
                    "primary_mac": "00:11:22:33:44:55",
                },
            },
        )
        assert request_response.status_code == 201
        enrollment_request = request_response.json()
        assert enrollment_request["company_id"] == company_id
        assert enrollment_request["status"] == "PENDING"

        list_response = await client.get(
            f"/api/v1/companies/{company_id}/enrollment-requests",
            headers={"X-Auditor-Session": auditor_session_id},
            params={"status": "PENDING"},
        )
        assert list_response.status_code == 200
        assert [item["enrollment_request_id"] for item in list_response.json()] == [
            enrollment_request["enrollment_request_id"],
        ]

        review_response = await client.post(
            (
                f"/api/v1/companies/{company_id}/enrollment-requests/"
                f"{enrollment_request['enrollment_request_id']}/review"
            ),
            headers={"X-Auditor-Session": auditor_session_id},
            json={"decision": "ACCEPT"},
        )
        assert review_response.status_code == 200
        reviewed_body = review_response.json()
        assert reviewed_body["status"] == "ACCEPTED"
        assert reviewed_body["link"]["company_id"] == company_id
        assert reviewed_body["link"]["device_id"] == "device-worker"
        assert reviewed_body["link"]["status"] == "ACTIVE"

        summary_response = await client.get(
            f"/api/v1/companies/{company_id}/summary",
            headers={"X-Auditor-Session": auditor_session_id},
        )
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert summary["linked_devices"] == 1
        assert summary["active_links"] == 1
        assert summary["pending_enrollment_requests"] == 0
        assert summary["active_auditor_sessions"] == 1


@pytest.mark.anyio
async def test_enrollment_code_requires_active_auditor_session() -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        company_id = await create_company(client)

        response = await client.post(
            f"/api/v1/companies/{company_id}/enrollment-codes",
            json={"ttl_seconds": 3600, "max_uses": 1},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Sesion de auditor requerida"


@pytest.mark.anyio
async def test_wrong_sms_code_does_not_create_auditor_session() -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        company_id = await create_company(client)
        agent_token = await provision_agent_token(client, device_id="device-auditor")
        await register_device(
            client,
            device_id="device-auditor",
            agent_token=agent_token,
            hostname="AUDITOR-LAPTOP",
        )
        access_response = await client.post(
            f"/api/v1/companies/{company_id}/auditor-access-requests",
            headers={"X-Agent-Token": agent_token},
            json={"device_id": "device-auditor"},
        )
        assert access_response.status_code == 201

        verify_response = await client.post(
            (
                f"/api/v1/companies/{company_id}/auditor-access-requests/"
                f"{access_response.json()['auditor_access_request_id']}/verify"
            ),
            headers={"X-Agent-Token": agent_token},
            json={"device_id": "device-auditor", "verification_code": "000000"},
        )

    assert verify_response.status_code == 422
    assert verify_response.json()["detail"] == "Codigo SMS invalido"


@pytest.mark.anyio
async def test_verified_auditor_request_cannot_be_replayed() -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        company_id = await create_company(client)
        agent_token = await provision_agent_token(client, device_id="device-auditor")
        await register_device(
            client,
            device_id="device-auditor",
            agent_token=agent_token,
            hostname="AUDITOR-LAPTOP",
        )
        access_response = await client.post(
            f"/api/v1/companies/{company_id}/auditor-access-requests",
            headers={"X-Agent-Token": agent_token},
            json={"device_id": "device-auditor"},
        )
        assert access_response.status_code == 201
        access_body = access_response.json()

        first_verify_response = await client.post(
            (
                f"/api/v1/companies/{company_id}/auditor-access-requests/"
                f"{access_body['auditor_access_request_id']}/verify"
            ),
            headers={"X-Agent-Token": agent_token},
            json={
                "device_id": "device-auditor",
                "verification_code": access_body["verification_code"],
            },
        )
        assert first_verify_response.status_code == 201

        replay_response = await client.post(
            (
                f"/api/v1/companies/{company_id}/auditor-access-requests/"
                f"{access_body['auditor_access_request_id']}/verify"
            ),
            headers={"X-Agent-Token": agent_token},
            json={
                "device_id": "device-auditor",
                "verification_code": access_body["verification_code"],
            },
        )

    assert replay_response.status_code == 422
    assert replay_response.json()["detail"] == "La solicitud de auditor ya fue verificada"


@pytest.mark.anyio
async def test_sms_code_is_blocked_after_max_failed_attempts() -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        company_id = await create_company(client)
        agent_token = await provision_agent_token(client, device_id="device-auditor")
        await register_device(
            client,
            device_id="device-auditor",
            agent_token=agent_token,
            hostname="AUDITOR-LAPTOP",
        )
        access_response = await client.post(
            f"/api/v1/companies/{company_id}/auditor-access-requests",
            headers={"X-Agent-Token": agent_token},
            json={"device_id": "device-auditor"},
        )
        assert access_response.status_code == 201
        access_body = access_response.json()
        verify_url = (
            f"/api/v1/companies/{company_id}/auditor-access-requests/"
            f"{access_body['auditor_access_request_id']}/verify"
        )

        invalid_responses = [
            await client.post(
                verify_url,
                headers={"X-Agent-Token": agent_token},
                json={"device_id": "device-auditor", "verification_code": "000000"},
            )
            for _attempt in range(5)
        ]
        valid_after_block_response = await client.post(
            verify_url,
            headers={"X-Agent-Token": agent_token},
            json={
                "device_id": "device-auditor",
                "verification_code": access_body["verification_code"],
            },
        )

    assert [response.status_code for response in invalid_responses] == [422] * 5
    assert invalid_responses[0].json()["detail"] == "Codigo SMS invalido"
    assert (
        invalid_responses[-1].json()["detail"]
        == "La solicitud de auditor fue bloqueada por intentos fallidos"
    )
    assert valid_after_block_response.status_code == 422
    assert valid_after_block_response.json()["detail"] == "La solicitud de auditor fue denegada"


def test_company_auth_schema_blocks_duplicate_pending_enrollment_requests() -> None:
    app = create_test_app()
    runtime_container = get_runtime_container(app)
    assert runtime_container.session_factory is not None

    requested_at = datetime.now(UTC)
    with runtime_container.session_factory() as session:
        session.add_all(
            [
                EnrollmentRequestModel(
                    enrollment_request_id="request-1",
                    company_id="company-1",
                    device_id="device-1",
                    requested_at=requested_at,
                    status="PENDING",
                    device_fingerprint_snapshot={"hostname": "worker-1"},
                ),
                EnrollmentRequestModel(
                    enrollment_request_id="request-2",
                    company_id="company-1",
                    device_id="device-1",
                    requested_at=requested_at,
                    status="PENDING",
                    device_fingerprint_snapshot={"hostname": "worker-1"},
                ),
            ],
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_company_auth_schema_blocks_duplicate_active_device_links() -> None:
    app = create_test_app()
    runtime_container = get_runtime_container(app)
    assert runtime_container.session_factory is not None

    linked_at = datetime.now(UTC)
    with runtime_container.session_factory() as session:
        session.add_all(
            [
                CompanyDeviceLinkModel(
                    company_device_link_id="link-1",
                    company_id="company-1",
                    device_id="device-1",
                    linked_at=linked_at,
                    status="ACTIVE",
                    revoked_by_device=False,
                ),
                CompanyDeviceLinkModel(
                    company_device_link_id="link-2",
                    company_id="company-1",
                    device_id="device-1",
                    linked_at=linked_at,
                    status="ACTIVE",
                    revoked_by_device=False,
                ),
            ],
        )

        with pytest.raises(IntegrityError):
            session.commit()
