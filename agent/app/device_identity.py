from dataclasses import dataclass
from hashlib import sha256
from platform import platform, system
from socket import AF_INET, gethostname
from uuid import getnode

import psutil

from agent.app.config import AGENT_VERSION, AgentSettings


@dataclass(frozen=True, slots=True)
class NetworkInterface:
    name: str
    local_ip: str | None
    mac_address: str | None
    is_up: bool


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    device_id: str
    hostname: str
    os_name: str
    agent_version: str
    interfaces: tuple[NetworkInterface, ...]

    @property
    def primary_interface(self) -> NetworkInterface | None:
        for interface in self.interfaces:
            if interface.is_up and interface.local_ip and not interface.local_ip.startswith("127."):
                return interface
        return self.interfaces[0] if self.interfaces else None

    @property
    def primary_local_ip(self) -> str | None:
        interface = self.primary_interface
        return interface.local_ip if interface else None

    @property
    def primary_mac_address(self) -> str | None:
        interface = self.primary_interface
        return interface.mac_address if interface else None

    @property
    def primary_interface_name(self) -> str | None:
        interface = self.primary_interface
        return interface.name if interface else None


class DeviceIdentityCollector:
    def __init__(self, settings: AgentSettings) -> None:
        self._settings = settings

    def collect(self) -> DeviceIdentity:
        hostname = gethostname()
        os_name = f"{system()} {platform()}"
        interfaces = tuple(self._collect_interfaces())
        return DeviceIdentity(
            device_id=self._settings.device_id or self._build_device_id(hostname, os_name),
            hostname=hostname,
            os_name=os_name,
            agent_version=AGENT_VERSION,
            interfaces=interfaces,
        )

    def _collect_interfaces(self) -> list[NetworkInterface]:
        try:
            addresses_by_interface = psutil.net_if_addrs()
            stats_by_interface = psutil.net_if_stats()
        except OSError:
            return []

        interfaces: list[NetworkInterface] = []

        for name, addresses in addresses_by_interface.items():
            local_ip: str | None = None
            mac_address: str | None = None

            for address in addresses:
                if address.family == AF_INET and local_ip is None:
                    local_ip = address.address
                elif self._is_mac_family(address.family) and mac_address is None:
                    mac_address = address.address

            stats = stats_by_interface.get(name)
            interfaces.append(
                NetworkInterface(
                    name=name,
                    local_ip=local_ip,
                    mac_address=mac_address,
                    is_up=bool(stats.isup) if stats else False,
                ),
            )

        return interfaces

    @staticmethod
    def _is_mac_family(family: object) -> bool:
        family_name = getattr(family, "name", "")
        return family_name in {"AF_LINK", "AF_PACKET"}

    @staticmethod
    def _build_device_id(hostname: str, os_name: str) -> str:
        raw_identity = f"{hostname}|{os_name}|{getnode()}".encode()
        digest = sha256(raw_identity).hexdigest()[:16]
        return f"device-{digest}"
