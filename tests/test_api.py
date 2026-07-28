from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from backend.app.audit.application.heartbeat_scheduler import detect_missed_heartbeats_once
from backend.app.main import create_app
from backend.app.shared.config import Settings

PROVISIONING_TOKEN = "test-provisioning-token"
AUDITOR_TOKEN = "test-auditor-token"
STRONG_PROVISIONING_TOKEN = "p" * 32
STRONG_AUDITOR_TOKEN = "a" * 32


def create_test_app(
    *,
    trusted_proxy_ips: str = "",
    app_env: str = "local",
    auditor_token: str = AUDITOR_TOKEN,
    provisioning_token: str = PROVISIONING_TOKEN,
) -> FastAPI:
    return create_app(
        settings=Settings(
            app_env=app_env,
            database_url="sqlite+pysqlite:///:memory:",
            persistence_backend="sqlalchemy",
            auditor_token=auditor_token,
            provisioning_token=provisioning_token,
            trusted_proxy_ips=trusted_proxy_ips,
        ),
        create_schema=True,
    )


async def provision_agent_token(
    client: httpx.AsyncClient,
    *,
    device_id: str = "device-1",
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


async def register_test_device(
    client: httpx.AsyncClient,
    *,
    agent_token: str,
    device_id: str = "device-1",
    hostname: str = "DEV-LAPTOP-001",
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/devices",
        headers={"X-Agent-Token": agent_token},
        json={
            "device_id": device_id,
            "hostname": hostname,
            "os_name": "linux",
            "agent_version": "0.1.0",
            "metadata": {"department": "development"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body, dict)
    return body


def auditor_headers() -> dict[str, str]:
    return {"X-Auditor-Token": AUDITOR_TOKEN}


@pytest.mark.anyio
async def test_health_check() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "persistence": "sqlalchemy",
        "database": "ok",
        "migration": "not_configured",
    }


@pytest.mark.anyio
async def test_api_docs_are_disabled_outside_local_environment() -> None:
    app = create_test_app(
        app_env="beta",
        auditor_token=STRONG_AUDITOR_TOKEN,
        provisioning_token=STRONG_PROVISIONING_TOKEN,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        docs_response = await client.get("/docs")
        openapi_response = await client.get("/openapi.json")

    assert docs_response.status_code == 404
    assert openapi_response.status_code == 404


def test_non_local_environment_requires_strong_shared_tokens() -> None:
    with pytest.raises(ValueError):
        Settings(
            app_env="beta",
            database_url="sqlite+pysqlite:///:memory:",
            auditor_token="corto",
            provisioning_token=STRONG_PROVISIONING_TOKEN,
        )


@pytest.mark.anyio
async def test_register_and_list_devices() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        body = await register_test_device(client, agent_token=agent_token)

        assert body["device_id"] == "device-1"

        list_response = await client.get("/api/v1/devices", headers=auditor_headers())
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1


@pytest.mark.anyio
async def test_ingest_and_search_network_events() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "https",
                "local_ip": "192.168.1.10",
                "public_ip": "203.0.113.10",
                "destination_host": "example.com",
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
                "http_method": "get",
                "http_status_code": 200,
                "bytes_sent": 512,
                "bytes_received": 2048,
                "network_interface": "eth0",
                "mac_address": "00:11:22:33:44:55",
                "local_username": "dev-user",
                "process_id": 4242,
                "process_name": "psql",
                "process_executable": "/usr/bin/psql",
                "service_name": "Base de datos produccion",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["protocol"] == "HTTPS"
        assert body["http_method"] == "GET"
        assert body["hostname"] == "DEV-LAPTOP-001"
        assert body["os_name"] == "linux"
        assert body["agent_version"] == "0.1.0"
        assert body["public_ip"] is None
        assert body["local_username"] == "dev-user"
        assert body["process_id"] == 4242
        assert body["process_name"] == "psql"
        assert body["process_executable"] == "/usr/bin/psql"
        assert body["service_name"] == "Base de datos produccion"
        assert body["request_metadata"]["agent_reported_public_ip"] == "203.0.113.10"

        search_response = await client.get(
            "/api/v1/audit/network-events",
            headers=auditor_headers(),
            params={"device_id": "device-1", "protocol": "https"},
        )
        assert search_response.status_code == 200
        assert len(search_response.json()) == 1


@pytest.mark.anyio
async def test_ingest_network_event_ignores_loopback_as_public_ip() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )

    assert response.status_code == 201
    assert response.json()["public_ip"] is None


@pytest.mark.anyio
async def test_ingest_network_event_ignores_untrusted_forwarded_public_ip() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        response = await client.post(
            "/api/v1/audit/network-events",
            headers={
                "X-Agent-Token": agent_token,
                "X-Forwarded-For": "192.168.1.10, 8.8.8.8",
            },
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )

    assert response.status_code == 201
    assert response.json()["public_ip"] is None


@pytest.mark.anyio
async def test_ingest_network_event_uses_forwarded_public_ip_from_trusted_proxy() -> None:
    transport = httpx.ASGITransport(app=create_test_app(trusted_proxy_ips="127.0.0.1"))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        response = await client.post(
            "/api/v1/audit/network-events",
            headers={
                "X-Agent-Token": agent_token,
                "X-Forwarded-For": "192.168.1.10, 8.8.8.8",
            },
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "public_ip": "1.1.1.1",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )

    assert response.status_code == 201
    assert response.json()["public_ip"] == "8.8.8.8"
    assert response.json()["request_metadata"]["agent_reported_public_ip"] == "1.1.1.1"


@pytest.mark.anyio
async def test_ingest_network_event_requires_registered_device() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "HOST-RECLAMADO",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "Dispositivo no registrado"


@pytest.mark.anyio
async def test_network_event_updates_device_last_seen_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    seen_at = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: seen_at,
        )

        response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:00:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
            },
        )
        assert response.status_code == 201

        list_response = await client.get("/api/v1/devices", headers=auditor_headers())
        assert list_response.status_code == 200
        assert datetime.fromisoformat(list_response.json()[0]["last_seen_at"]) == seen_at


@pytest.mark.anyio
async def test_ingest_and_search_lifecycle_events() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        response = await client.post(
            "/api/v1/audit/lifecycle-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "event_type": "AGENT_MISSED_HEARTBEAT",
                "occurred_at": "2026-07-27T14:03:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
                "public_ip": "203.0.113.10",
                "last_seen_at": "2026-07-27T14:00:00-05:00",
                "detected_at": "2026-07-27T14:03:00-05:00",
                "downtime_seconds": 180,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["event_type"] == "AGENT_MISSED_HEARTBEAT"
        assert body["public_ip"] is None

        search_response = await client.get(
            "/api/v1/audit/lifecycle-events",
            headers=auditor_headers(),
            params={"device_id": "device-1", "event_type": "AGENT_MISSED_HEARTBEAT"},
        )
        assert search_response.status_code == 200
        assert len(search_response.json()) == 1


@pytest.mark.anyio
async def test_query_incident_window_groups_activity_and_missing_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    registered_at = datetime(2026, 7, 27, 13, 0, tzinfo=UTC)
    reported_at = datetime(2026, 7, 27, 14, 3, tzinfo=UTC)
    monkeypatch.setattr(
        "backend.app.devices.application.register_device.utc_now",
        lambda: registered_at,
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        inactive_agent_token = await provision_agent_token(client, device_id="device-2")
        await register_test_device(client, agent_token=agent_token)
        await register_test_device(
            client,
            agent_token=inactive_agent_token,
            device_id="device-2",
            hostname="DEV-LAPTOP-002",
        )
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: reported_at,
        )

        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": reported_at.isoformat(),
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "public_ip": "203.0.113.10",
                "destination_host": "db-produccion.local",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
                "local_username": "dev-user",
                "process_id": 4242,
                "process_name": "psql",
                "service_name": "Base de datos produccion",
            },
        )
        assert network_response.status_code == 201
        lifecycle_response = await client.post(
            "/api/v1/audit/lifecycle-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "event_type": "AGENT_STOPPED",
                "occurred_at": (reported_at + timedelta(minutes=1)).isoformat(),
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
            },
        )
        assert lifecycle_response.status_code == 201

        response = await client.get(
            "/api/v1/audit/incident-window",
            headers=auditor_headers(),
            params={
                "from": "2026-07-27T14:00:00+00:00",
                "to": "2026-07-27T14:15:00+00:00",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["active_devices"][0]["device_id"] == "device-1"
    assert body["devices_without_report"][0]["device_id"] == "device-2"
    assert body["network_events"][0]["destination_host"] == "db-produccion.local"
    assert body["network_events"][0]["process_name"] == "psql"
    assert body["network_events"][0]["service_name"] == "Base de datos produccion"
    assert body["lifecycle_events"][0]["event_type"] == "AGENT_STOPPED"


@pytest.mark.anyio
async def test_query_incident_window_active_devices_do_not_depend_on_event_limit() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        second_agent_token = await provision_agent_token(client, device_id="device-2")
        await register_test_device(client, agent_token=agent_token)
        await register_test_device(
            client,
            agent_token=second_agent_token,
            device_id="device-2",
            hostname="DEV-LAPTOP-002",
        )

        first_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:04:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )
        assert first_response.status_code == 201
        second_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": second_agent_token},
            json={
                "occurred_at": "2026-07-27T14:03:00+00:00",
                "device_id": "device-2",
                "hostname": "HOSTNAME-RECLAMADO",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.11",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )
        assert second_response.status_code == 201

        response = await client.get(
            "/api/v1/audit/incident-window",
            headers=auditor_headers(),
            params={
                "from": "2026-07-27T14:00:00+00:00",
                "to": "2026-07-27T14:15:00+00:00",
                "limit": 1,
            },
        )

    assert response.status_code == 200
    body = response.json()
    active_device_ids = {device["device_id"] for device in body["active_devices"]}
    assert active_device_ids == {"device-1", "device-2"}
    assert len(body["network_events"]) == 1


@pytest.mark.anyio
async def test_query_device_movements_combines_network_and_lifecycle_events() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T14:03:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_host": "db-produccion.local",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
                "local_username": "dev-user",
                "process_id": 4242,
                "process_name": "psql",
                "service_name": "Base de datos produccion",
            },
        )
        assert network_response.status_code == 201
        lifecycle_response = await client.post(
            "/api/v1/audit/lifecycle-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "event_type": "AGENT_STOPPED",
                "occurred_at": "2026-07-27T14:04:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
                "reason": "stop requested",
            },
        )
        assert lifecycle_response.status_code == 201

        response = await client.get(
            "/api/v1/audit/device-movements",
            headers=auditor_headers(),
            params={"device_id": "device-1", "limit": 10},
        )

    assert response.status_code == 200
    body = response.json()
    assert [movement["movement_type"] for movement in body] == [
        "AGENT_STOPPED",
        "NETWORK_CONNECTION",
    ]
    assert body[0]["summary"] == "AGENT_STOPPED: stop requested"
    assert body[1]["summary"] == "Base de datos produccion:5432"
    assert body[1]["process_name"] == "psql"
    assert body[1]["local_username"] == "dev-user"


@pytest.mark.anyio
async def test_query_incident_window_accepts_exact_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    reported_at = datetime(2026, 7, 27, 14, 3, tzinfo=UTC)
    monkeypatch.setattr(
        "backend.app.devices.application.register_device.utc_now",
        lambda: reported_at,
    )
    monkeypatch.setattr(
        "backend.app.audit.application.record_agent_activity.utc_now",
        lambda: reported_at,
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": reported_at.isoformat(),
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "10.0.0.25",
                "destination_port": 5432,
            },
        )
        assert network_response.status_code == 201

        response = await client.get(
            "/api/v1/audit/incident-window",
            headers=auditor_headers(),
            params={
                "at": "2026-07-27T09:03:00-05:00",
                "window_seconds": 120,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["from_datetime"] == "2026-07-27T14:02:00Z"
    assert body["to_datetime"] == "2026-07-27T14:04:00Z"
    assert body["network_events"][0]["device_id"] == "device-1"


@pytest.mark.anyio
async def test_lifecycle_heartbeat_updates_device_last_seen_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    seen_at = datetime(2026, 7, 27, 15, 5, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: seen_at,
        )

        response = await client.post(
            "/api/v1/audit/lifecycle-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "event_type": "AGENT_HEARTBEAT",
                "occurred_at": "2026-07-27T14:03:00-05:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
            },
        )
        assert response.status_code == 201

        list_response = await client.get("/api/v1/devices", headers=auditor_headers())
        assert list_response.status_code == 200
        assert datetime.fromisoformat(list_response.json()[0]["last_seen_at"]) == seen_at


@pytest.mark.anyio
async def test_detect_missed_heartbeats_creates_lifecycle_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    last_seen_at = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    detected_at = datetime(2026, 7, 27, 15, 4, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: last_seen_at,
        )
        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T15:00:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
            },
        )
        assert network_response.status_code == 201
        monkeypatch.setattr(
            "backend.app.audit.application.detect_missed_heartbeats.utc_now",
            lambda: detected_at,
        )

        response = await client.post(
            "/api/v1/audit/lifecycle-events/detect-missed-heartbeats",
            headers={"X-Provisioning-Token": PROVISIONING_TOKEN},
        )

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["event_type"] == "AGENT_MISSED_HEARTBEAT"
        assert body[0]["last_seen_at"] == "2026-07-27T15:00:00Z"
        assert body[0]["detected_at"] == "2026-07-27T15:04:00Z"
        assert body[0]["downtime_seconds"] == 240

        repeated_response = await client.post(
            "/api/v1/audit/lifecycle-events/detect-missed-heartbeats",
            headers={"X-Provisioning-Token": PROVISIONING_TOKEN},
        )
        assert repeated_response.status_code == 200
        assert repeated_response.json() == []


@pytest.mark.anyio
async def test_scheduled_missed_heartbeat_detector_reuses_runtime_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_test_app()
    transport = httpx.ASGITransport(app=app)
    last_seen_at = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    detected_at = datetime(2026, 7, 27, 15, 4, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: last_seen_at,
        )
        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T15:00:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
            },
        )
        assert network_response.status_code == 201
        monkeypatch.setattr(
            "backend.app.audit.application.detect_missed_heartbeats.utc_now",
            lambda: detected_at,
        )

        detected_count = detect_missed_heartbeats_once(app.state.container)

        assert detected_count == 1
        lifecycle_response = await client.get(
            "/api/v1/audit/lifecycle-events",
            headers=auditor_headers(),
            params={"device_id": "device-1", "event_type": "AGENT_MISSED_HEARTBEAT"},
        )

    assert lifecycle_response.status_code == 200
    lifecycle_events = lifecycle_response.json()
    assert len(lifecycle_events) == 1
    assert lifecycle_events[0]["detected_at"] == "2026-07-27T15:04:00Z"


@pytest.mark.anyio
async def test_heartbeat_after_missed_heartbeat_records_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    last_seen_at = datetime(2026, 7, 27, 15, 0, tzinfo=UTC)
    detected_at = datetime(2026, 7, 27, 15, 4, tzinfo=UTC)
    recovered_at = datetime(2026, 7, 27, 15, 5, tzinfo=UTC)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        agent_token = await provision_agent_token(client)
        await register_test_device(client, agent_token=agent_token)
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: last_seen_at,
        )
        network_response = await client.post(
            "/api/v1/audit/network-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "occurred_at": "2026-07-27T15:00:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "protocol": "tcp",
                "local_ip": "192.168.1.10",
                "destination_ip": "93.184.216.34",
                "destination_port": 443,
            },
        )
        assert network_response.status_code == 201
        monkeypatch.setattr(
            "backend.app.audit.application.detect_missed_heartbeats.utc_now",
            lambda: detected_at,
        )
        missed_response = await client.post(
            "/api/v1/audit/lifecycle-events/detect-missed-heartbeats",
            headers={"X-Provisioning-Token": PROVISIONING_TOKEN},
        )
        assert missed_response.status_code == 200
        monkeypatch.setattr(
            "backend.app.audit.application.record_agent_activity.utc_now",
            lambda: recovered_at,
        )

        heartbeat_response = await client.post(
            "/api/v1/audit/lifecycle-events",
            headers={"X-Agent-Token": agent_token},
            json={
                "event_type": "AGENT_HEARTBEAT",
                "occurred_at": "2026-07-27T15:05:00+00:00",
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "agent_version": "0.1.0",
                "local_ip": "192.168.1.10",
            },
        )

        assert heartbeat_response.status_code == 201
        recovered_response = await client.get(
            "/api/v1/audit/lifecycle-events",
            headers=auditor_headers(),
            params={"device_id": "device-1", "event_type": "AGENT_RECOVERED"},
        )
        assert recovered_response.status_code == 200
        recovered_events = recovered_response.json()
        assert len(recovered_events) == 1
        assert recovered_events[0]["last_seen_at"] == "2026-07-27T15:00:00Z"
        assert recovered_events[0]["detected_at"] == "2026-07-27T15:05:00Z"
        assert recovered_events[0]["downtime_seconds"] == 300

        list_response = await client.get("/api/v1/devices", headers=auditor_headers())
        assert list_response.status_code == 200
        assert datetime.fromisoformat(list_response.json()[0]["last_seen_at"]) == recovered_at


@pytest.mark.anyio
async def test_agent_writes_require_valid_token() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing_token_response = await client.post(
            "/api/v1/devices",
            json={
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
            },
        )
        assert missing_token_response.status_code == 401

        await provision_agent_token(client)
        invalid_token_response = await client.post(
            "/api/v1/devices",
            headers={"X-Agent-Token": "token-incorrecto"},
            json={
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
            },
        )
        assert invalid_token_response.status_code == 401


@pytest.mark.anyio
async def test_audit_queries_require_auditor_token() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        devices_response = await client.get("/api/v1/devices")
        network_events_response = await client.get("/api/v1/audit/network-events")
        lifecycle_events_response = await client.get("/api/v1/audit/lifecycle-events")
        device_movements_response = await client.get(
            "/api/v1/audit/device-movements",
            params={"device_id": "device-1"},
        )
        incident_window_response = await client.get(
            "/api/v1/audit/incident-window",
            params={
                "from": "2026-07-27T14:00:00+00:00",
                "to": "2026-07-27T14:15:00+00:00",
            },
        )

    assert devices_response.status_code == 401
    assert network_events_response.status_code == 401
    assert lifecycle_events_response.status_code == 401
    assert device_movements_response.status_code == 401
    assert incident_window_response.status_code == 401


@pytest.mark.anyio
async def test_provisioning_requires_admin_token() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/devices/agent-credentials",
            json={"device_id": "device-1"},
        )

    assert response.status_code == 401
