from datetime import UTC, datetime
from typing import Any, Protocol

from auditor.app.state import AuditorSessionState

AUDIT_EXPORT_FORMAT_VERSION = "audit-export/v1"


class AuditExportClient(Protocol):
    def search_network_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def search_lifecycle_events(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def search_device_movements(
        self,
        *,
        auditor_session_id: str,
        device_id: str,
        filters: dict[str, object | None],
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_incident_window(
        self,
        *,
        auditor_session_id: str,
        filters: dict[str, object | None],
    ) -> dict[str, Any]:
        raise NotImplementedError


def build_audit_export(
    client: AuditExportClient,
    session: AuditorSessionState,
    *,
    from_datetime: str,
    to_datetime: str,
    device_id: str | None = None,
    limit: int = 500,
    exported_at: datetime | None = None,
) -> dict[str, Any]:
    event_filters: dict[str, object | None] = {
        "device_id": device_id,
        "from": from_datetime,
        "to": to_datetime,
        "limit": limit,
    }
    window_filters: dict[str, object | None] = {
        "from": from_datetime,
        "to": to_datetime,
        "limit": limit,
    }
    movement_filters: dict[str, object | None] = {
        "from": from_datetime,
        "to": to_datetime,
        "limit": limit,
    }

    network_events = client.search_network_events(
        auditor_session_id=session.auditor_session_id,
        filters=event_filters,
    )
    lifecycle_events = client.search_lifecycle_events(
        auditor_session_id=session.auditor_session_id,
        filters=event_filters,
    )
    device_movements = (
        client.search_device_movements(
            auditor_session_id=session.auditor_session_id,
            device_id=device_id,
            filters=movement_filters,
        )
        if device_id is not None
        else []
    )
    incident_window = client.query_incident_window(
        auditor_session_id=session.auditor_session_id,
        filters=window_filters,
    )

    exported_time = exported_at or datetime.now(UTC)
    return {
        "format_version": AUDIT_EXPORT_FORMAT_VERSION,
        "metadata": {
            "exported_at": exported_time.isoformat(),
            "company": {
                "company_id": session.company_id,
            },
            "auditor_session": {
                "auditor_session_id": session.auditor_session_id,
                "device_id": session.device_id,
                "expires_at": session.expires_at,
                "scopes": list(session.scopes),
            },
            "filters": {
                "from": from_datetime,
                "to": to_datetime,
                "device_id": device_id,
                "limit": limit,
            },
        },
        "events": {
            "network_events": network_events,
            "lifecycle_events": lifecycle_events,
            "device_movements": device_movements,
            "incident_window": incident_window,
        },
    }
