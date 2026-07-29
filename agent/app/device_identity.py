from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from platform import platform, system
from socket import AF_INET, gethostname
from typing import Any
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
        raw_identity = f"{hostname}|{os_name}|{_machine_fingerprint()}".encode()
        digest = sha256(raw_identity).hexdigest()[:16]
        return f"device-{digest}"


def _machine_fingerprint() -> str:
    machine_id = _linux_machine_id()
    if machine_id:
        return machine_id

    windows_machine_guid = _windows_machine_guid()
    if windows_machine_guid:
        return windows_machine_guid

    return str(getnode())


def _linux_machine_id() -> str | None:
    for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return None


def _windows_machine_guid() -> str | None:
    try:
        import winreg
    except ImportError:
        return None

    winreg_module: Any = winreg
    try:
        with winreg_module.OpenKey(
            winreg_module.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        ) as key:
            value, _value_type = winreg_module.QueryValueEx(key, "MachineGuid")
    except OSError:
        return None

    return value.strip() if isinstance(value, str) and value.strip() else None
