import httpx
import pytest
from fastapi import FastAPI

from backend.app.main import create_app
from backend.app.shared.config import Settings


def create_test_app() -> FastAPI:
    return create_app(
        settings=Settings(
            database_url="sqlite+pysqlite:///:memory:",
            persistence_backend="sqlalchemy",
        ),
        create_schema=True,
    )


@pytest.mark.anyio
async def test_health_check() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_register_and_list_devices() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/devices",
            json={
                "device_id": "device-1",
                "hostname": "DEV-LAPTOP-001",
                "os_name": "linux",
                "agent_version": "0.1.0",
                "metadata": {"department": "development"},
            },
        )

        assert response.status_code == 201
        assert response.json()["device_id"] == "device-1"

        list_response = await client.get("/api/v1/devices")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1


@pytest.mark.anyio
async def test_ingest_and_search_network_events() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/audit/network-events",
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
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["protocol"] == "HTTPS"
        assert body["http_method"] == "GET"

        search_response = await client.get(
            "/api/v1/audit/network-events",
            params={"device_id": "device-1", "protocol": "https"},
        )
        assert search_response.status_code == 200
        assert len(search_response.json()) == 1


@pytest.mark.anyio
async def test_ingest_and_search_lifecycle_events() -> None:
    transport = httpx.ASGITransport(app=create_test_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/audit/lifecycle-events",
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
        assert response.json()["event_type"] == "AGENT_MISSED_HEARTBEAT"

        search_response = await client.get(
            "/api/v1/audit/lifecycle-events",
            params={"device_id": "device-1", "event_type": "AGENT_MISSED_HEARTBEAT"},
        )
        assert search_response.status_code == 200
        assert len(search_response.json()) == 1
