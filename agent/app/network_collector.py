from dataclasses import dataclass
from datetime import datetime
from socket import SOCK_DGRAM, SOCK_STREAM
from typing import Any

import psutil

from agent.app.clock import to_iso, utc_now
from agent.app.device_identity import DeviceIdentity, NetworkInterface


@dataclass(frozen=True, slots=True)
class ObservedNetworkConnection:
    occurred_at: datetime
    protocol: str
    local_ip: str | None
    local_port: int | None
    destination_ip: str | None
    destination_port: int | None
    status: str | None
    network_interface: str | None
    mac_address: str | None

    @property
    def signature(self) -> str:
        return "|".join(
            [
                self.protocol,
                self.local_ip or "",
                str(self.local_port or ""),
                self.destination_ip or "",
                str(self.destination_port or ""),
            ],
        )

    def to_backend_payload(self, identity: DeviceIdentity) -> dict[str, object]:
        return {
            "occurred_at": to_iso(self.occurred_at),
            "device_id": identity.device_id,
            "hostname": identity.hostname,
            "os_name": identity.os_name,
            "agent_version": identity.agent_version,
            "protocol": self.protocol,
            "local_ip": self.local_ip,
            "destination_ip": self.destination_ip,
            "destination_port": self.destination_port,
            "bytes_sent": 0,
            "bytes_received": 0,
            "network_interface": self.network_interface,
            "mac_address": self.mac_address,
            "request_metadata": {
                "local_port": str(self.local_port or ""),
                "connection_status": self.status or "",
                "collector": "psutil.net_connections",
                "byte_accounting": "not_available_per_connection",
            },
            "response_metadata": {},
        }


class NetworkConnectionCollector:
    def collect(self, identity: DeviceIdentity) -> list[ObservedNetworkConnection]:
        try:
            raw_connections = psutil.net_connections(kind="inet")
        except OSError:
            return []

        observed_at = utc_now()
        connections: list[ObservedNetworkConnection] = []
        for raw_connection in raw_connections:
            destination_ip = self._address_host(raw_connection.raddr)
            destination_port = self._address_port(raw_connection.raddr)
            if destination_ip is None or self._is_loopback(destination_ip):
                continue

            local_ip = self._address_host(raw_connection.laddr)
            local_port = self._address_port(raw_connection.laddr)
            interface = self._find_interface(identity, local_ip)
            interface_name = interface.name if interface else identity.primary_interface_name
            mac_address = interface.mac_address if interface else identity.primary_mac_address
            connections.append(
                ObservedNetworkConnection(
                    occurred_at=observed_at,
                    protocol=self._protocol_name(raw_connection.type),
                    local_ip=local_ip,
                    local_port=local_port,
                    destination_ip=destination_ip,
                    destination_port=destination_port,
                    status=getattr(raw_connection, "status", None) or None,
                    network_interface=interface_name,
                    mac_address=mac_address,
                ),
            )

        return connections

    @staticmethod
    def _address_host(address: Any) -> str | None:
        if not address:
            return None
        value = getattr(address, "ip", None)
        if isinstance(value, str):
            return value
        if isinstance(address, tuple) and address:
            host = address[0]
            return host if isinstance(host, str) else None
        return None

    @staticmethod
    def _address_port(address: Any) -> int | None:
        if not address:
            return None
        value = getattr(address, "port", None)
        if isinstance(value, int):
            return value
        if isinstance(address, tuple) and len(address) > 1:
            port = address[1]
            return port if isinstance(port, int) else None
        return None

    @staticmethod
    def _protocol_name(socket_type: object) -> str:
        if socket_type == SOCK_STREAM:
            return "TCP"
        if socket_type == SOCK_DGRAM:
            return "UDP"
        return "IP"

    @staticmethod
    def _is_loopback(ip_address: str) -> bool:
        return ip_address.startswith("127.") or ip_address == "::1"

    @staticmethod
    def _find_interface(
        identity: DeviceIdentity,
        local_ip: str | None,
    ) -> NetworkInterface | None:
        if local_ip is None:
            return None
        for interface in identity.interfaces:
            if interface.local_ip == local_ip:
                return interface
        return None
