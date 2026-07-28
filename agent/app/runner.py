from collections.abc import Callable
from datetime import datetime
from signal import SIGINT, SIGTERM, signal
from threading import Event
from time import monotonic
from typing import Any, Protocol

from agent.app.clock import to_iso, utc_now
from agent.app.config import AgentSettings
from agent.app.device_identity import DeviceIdentity, DeviceIdentityCollector
from agent.app.local_queue import QueuedAuditApiClient
from agent.app.network_collector import NetworkConnectionCollector, ObservedNetworkConnection
from agent.app.service_map import ServiceMap
from agent.app.transport import AuditApiClient


class AgentConfigurationError(RuntimeError):
    pass


class IdentityCollector(Protocol):
    def collect(self) -> DeviceIdentity:
        raise NotImplementedError


class ConnectionCollector(Protocol):
    def collect(self, identity: DeviceIdentity) -> list[ObservedNetworkConnection]:
        raise NotImplementedError


class AgentApiClient(Protocol):
    def register_device(self, identity: DeviceIdentity) -> dict[str, Any]:
        raise NotImplementedError

    def send_lifecycle_event(
        self,
        identity: DeviceIdentity,
        event_type: str,
        occurred_at: str,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def send_network_event(self, payload: dict[str, object]) -> dict[str, Any]:
        raise NotImplementedError


class StopSignal(Protocol):
    def wait(self, timeout: float | None = None) -> bool:
        raise NotImplementedError

    def set(self) -> None:
        raise NotImplementedError

    def is_set(self) -> bool:
        raise NotImplementedError


class AgentRunner:
    def __init__(
        self,
        settings: AgentSettings,
        identity_collector: IdentityCollector | None = None,
        network_collector: ConnectionCollector | None = None,
        api_client: AgentApiClient | None = None,
        stop_signal: StopSignal | None = None,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._identity_collector = identity_collector or DeviceIdentityCollector(settings)
        self._network_collector = network_collector or NetworkConnectionCollector(
            ServiceMap.from_file(settings.service_map_file),
        )
        self._api_client = api_client or self._build_api_client(settings)
        self._stop_requested = stop_signal or Event()
        self._monotonic_clock = monotonic_clock or monotonic
        self._last_sent_network_events: dict[str, datetime] = {}

    def run_once(self) -> None:
        identity = self._bootstrap()
        self._send_lifecycle(identity, "AGENT_HEARTBEAT")
        self._collect_and_send_network_events(identity)
        self._shutdown(identity, reason="one-shot execution finished")

    def run_forever(self) -> None:
        identity = self._bootstrap()
        self._install_signal_handlers(identity)
        heartbeat_interval = self._positive_interval(self._settings.heartbeat_interval_seconds)
        scan_interval = self._positive_interval(self._settings.scan_interval_seconds)
        now = self._monotonic_clock()
        next_heartbeat_at = now + heartbeat_interval
        next_scan_at = now + scan_interval

        while not self._stop_requested.is_set():
            now = self._monotonic_clock()
            if now >= next_heartbeat_at:
                self._send_lifecycle(identity, "AGENT_HEARTBEAT")
                next_heartbeat_at = now + heartbeat_interval

            if now >= next_scan_at:
                self._collect_and_send_network_events(identity)
                next_scan_at = now + scan_interval

            next_task_at = min(next_heartbeat_at, next_scan_at)
            wait_seconds = max(next_task_at - self._monotonic_clock(), 0.0)
            self._stop_requested.wait(wait_seconds)

        self._shutdown(identity, reason="stop requested")

    def request_stop(self) -> None:
        self._stop_requested.set()

    @staticmethod
    def _require_agent_token(settings: AgentSettings) -> str:
        if not settings.agent_token:
            raise AgentConfigurationError("AGENT_TOKEN es obligatorio para reportar al backend")
        return settings.agent_token

    @classmethod
    def _build_api_client(cls, settings: AgentSettings) -> AgentApiClient:
        client = AuditApiClient(
            settings.backend_url,
            agent_token=cls._require_agent_token(settings),
            agent_token_header=settings.agent_token_header,
            timeout_seconds=settings.request_timeout_seconds,
        )
        return QueuedAuditApiClient.from_audit_api_client(
            client,
            settings.queue_file,
            retry_backoff_seconds=settings.request_retry_backoff_seconds,
        )

    def _bootstrap(self) -> DeviceIdentity:
        identity = self._identity_collector.collect()
        self._api_client.register_device(identity)
        self._send_lifecycle(identity, "AGENT_STARTED")
        return identity

    def _shutdown(self, identity: DeviceIdentity, *, reason: str) -> None:
        self._send_lifecycle(identity, "AGENT_STOPPING", reason=reason)
        self._send_lifecycle(identity, "AGENT_STOPPED", reason=reason)

    def _send_lifecycle(
        self,
        identity: DeviceIdentity,
        event_type: str,
        *,
        reason: str | None = None,
    ) -> None:
        self._api_client.send_lifecycle_event(
            identity,
            event_type,
            to_iso(utc_now()),
            reason=reason,
        )

    def _collect_and_send_network_events(self, identity: DeviceIdentity) -> None:
        for connection in self._network_collector.collect(identity):
            if self._should_send_network_event(connection):
                self._api_client.send_network_event(connection.to_backend_payload(identity))
                self._last_sent_network_events[connection.signature] = connection.occurred_at

    def _should_send_network_event(self, connection: ObservedNetworkConnection) -> bool:
        last_sent_at = self._last_sent_network_events.get(connection.signature)
        if last_sent_at is None:
            return True
        elapsed = connection.occurred_at - last_sent_at
        return elapsed.total_seconds() >= self._settings.network_event_dedup_seconds

    @staticmethod
    def _positive_interval(interval_seconds: int) -> float:
        return float(max(interval_seconds, 1))

    def _install_signal_handlers(self, _identity: DeviceIdentity) -> None:
        def handle_signal(_signal_number: int, _frame: object) -> None:
            self.request_stop()

        signal(SIGINT, handle_signal)
        signal(SIGTERM, handle_signal)
