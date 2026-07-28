import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from agent.app.device_identity import DeviceIdentity
from agent.app.transport import (
    AgentTransportError,
    AuditApiClient,
    build_device_registration_payload,
    build_lifecycle_event_payload,
)


@dataclass(frozen=True, slots=True)
class QueuedRequest:
    path: str
    payload: dict[str, Any]


class PostJsonClient(Protocol):
    def post_json(self, path: str, payload: dict[str, Any] | dict[str, object]) -> dict[str, Any]:
        raise NotImplementedError


class LocalAgentRequestQueue:
    def __init__(self, queue_file: Path) -> None:
        self._queue_file = queue_file

    def enqueue(self, request: QueuedRequest) -> None:
        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        with self._queue_file.open("a", encoding="utf-8") as file:
            file.write(json.dumps(self._request_to_json(request), sort_keys=True))
            file.write("\n")

    def read_all(self) -> list[QueuedRequest]:
        if not self._queue_file.exists():
            return []

        requests: list[QueuedRequest] = []
        for line in self._queue_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            decoded = json.loads(line)
            if not isinstance(decoded, dict):
                continue
            requests.append(self._request_from_json(decoded))
        return requests

    def replace_all(self, requests: list[QueuedRequest]) -> None:
        if not requests:
            self._queue_file.unlink(missing_ok=True)
            return

        self._queue_file.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            json.dumps(self._request_to_json(request), sort_keys=True)
            for request in requests
        )
        self._queue_file.write_text(f"{content}\n", encoding="utf-8")

    @staticmethod
    def _request_to_json(request: QueuedRequest) -> dict[str, Any]:
        return {"path": request.path, "payload": request.payload}

    @staticmethod
    def _request_from_json(raw_request: dict[str, Any]) -> QueuedRequest:
        path = raw_request.get("path")
        payload = raw_request.get("payload")
        if not isinstance(path, str) or not isinstance(payload, dict):
            raise ValueError("Registro de cola local invalido")
        return QueuedRequest(path=path, payload=payload)


class QueuedAuditApiClient:
    def __init__(
        self,
        client: PostJsonClient,
        queue: LocalAgentRequestQueue,
        *,
        retry_backoff_seconds: int,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._client = client
        self._queue = queue
        self._retry_backoff_seconds = max(retry_backoff_seconds, 1)
        self._monotonic_clock = monotonic_clock or monotonic
        self._next_flush_at = 0.0

    @classmethod
    def from_audit_api_client(
        cls,
        client: AuditApiClient,
        queue_file: Path,
        *,
        retry_backoff_seconds: int,
    ) -> "QueuedAuditApiClient":
        return cls(
            client,
            LocalAgentRequestQueue(queue_file),
            retry_backoff_seconds=retry_backoff_seconds,
        )

    def register_device(self, identity: DeviceIdentity) -> dict[str, Any]:
        return self._post_or_queue(
            QueuedRequest(
                path="/api/v1/devices",
                payload=build_device_registration_payload(identity),
            ),
        )

    def send_lifecycle_event(
        self,
        identity: DeviceIdentity,
        event_type: str,
        occurred_at: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self._post_or_queue(
            QueuedRequest(
                path="/api/v1/audit/lifecycle-events",
                payload=build_lifecycle_event_payload(
                    identity,
                    event_type,
                    occurred_at,
                    reason=reason,
                ),
            ),
        )

    def send_network_event(self, payload: dict[str, object]) -> dict[str, Any]:
        return self._post_or_queue(
            QueuedRequest(
                path="/api/v1/audit/network-events",
                payload=dict(payload),
            ),
        )

    def _post_or_queue(self, request: QueuedRequest) -> dict[str, Any]:
        if not self.flush():
            self._queue.enqueue(request)
            return {}

        try:
            return self._client.post_json(request.path, request.payload)
        except AgentTransportError as exc:
            if not exc.retryable:
                raise
            self._queue.enqueue(request)
            self._schedule_next_flush()
            return {}

    def flush(self) -> bool:
        queued_requests = self._queue.read_all()
        if not queued_requests:
            self._next_flush_at = 0.0
            return True

        if self._monotonic_clock() < self._next_flush_at:
            return False

        remaining_requests: list[QueuedRequest] = []
        for index, request in enumerate(queued_requests):
            try:
                self._client.post_json(request.path, request.payload)
            except AgentTransportError as exc:
                if not exc.retryable:
                    raise
                remaining_requests.extend(queued_requests[index:])
                self._queue.replace_all(remaining_requests)
                self._schedule_next_flush()
                return False

        self._queue.replace_all([])
        self._next_flush_at = 0.0
        return True

    def _schedule_next_flush(self) -> None:
        self._next_flush_at = self._monotonic_clock() + self._retry_backoff_seconds
