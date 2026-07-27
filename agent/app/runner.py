from signal import SIGINT, SIGTERM, signal
from threading import Event

from agent.app.clock import to_iso, utc_now
from agent.app.config import AgentSettings
from agent.app.device_identity import DeviceIdentity, DeviceIdentityCollector
from agent.app.transport import AuditApiClient


class AgentRunner:
    def __init__(
        self,
        settings: AgentSettings,
        identity_collector: DeviceIdentityCollector | None = None,
        api_client: AuditApiClient | None = None,
    ) -> None:
        self._settings = settings
        self._identity_collector = identity_collector or DeviceIdentityCollector(settings)
        self._api_client = api_client or AuditApiClient(
            settings.backend_url,
            timeout_seconds=settings.request_timeout_seconds,
        )
        self._stop_requested = Event()

    def run_once(self) -> None:
        identity = self._bootstrap()
        self._send_lifecycle(identity, "AGENT_HEARTBEAT")
        self._shutdown(identity, reason="one-shot execution finished")

    def run_forever(self) -> None:
        identity = self._bootstrap()
        self._install_signal_handlers(identity)

        while not self._stop_requested.wait(self._settings.heartbeat_interval_seconds):
            self._send_lifecycle(identity, "AGENT_HEARTBEAT")

        self._shutdown(identity, reason="stop requested")

    def request_stop(self) -> None:
        self._stop_requested.set()

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

    def _install_signal_handlers(self, _identity: DeviceIdentity) -> None:
        def handle_signal(_signal_number: int, _frame: object) -> None:
            self.request_stop()

        signal(SIGINT, handle_signal)
        signal(SIGTERM, handle_signal)
