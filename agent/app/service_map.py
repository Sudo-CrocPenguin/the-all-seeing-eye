import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ServiceMapEntry:
    name: str
    destination_ip: str
    destination_port: int | None = None
    destination_host: str | None = None

    @property
    def key(self) -> str:
        port = str(self.destination_port or "*")
        return f"{self.destination_ip}:{port}"


class ServiceMap:
    def __init__(self, entries: list[ServiceMapEntry] | None = None) -> None:
        self._items: dict[str, ServiceMapEntry] = {}
        for entry in entries or []:
            self._items[entry.key] = entry

    @classmethod
    def from_file(cls, path: Path | None) -> "ServiceMap":
        if path is None:
            return cls()
        try:
            raw_content = path.read_text(encoding="utf-8")
        except OSError:
            return cls()

        decoded = json.loads(raw_content)
        if isinstance(decoded, dict):
            raw_entries = decoded.get("services", decoded)
        else:
            raw_entries = decoded

        return cls(_parse_entries(raw_entries))

    def find(
        self,
        destination_ip: str | None,
        destination_port: int | None,
    ) -> ServiceMapEntry | None:
        if destination_ip is None:
            return None

        if destination_port is not None:
            exact_match = self._items.get(f"{destination_ip}:{destination_port}")
            if exact_match is not None:
                return exact_match

        return self._items.get(f"{destination_ip}:*")


def _parse_entries(raw_entries: Any) -> list[ServiceMapEntry]:
    if isinstance(raw_entries, dict):
        return _parse_dict_entries(raw_entries)
    if isinstance(raw_entries, list):
        return [_parse_object_entry(item) for item in raw_entries if isinstance(item, dict)]
    return []


def _parse_dict_entries(raw_entries: dict[Any, Any]) -> list[ServiceMapEntry]:
    entries: list[ServiceMapEntry] = []
    for raw_key, raw_name in raw_entries.items():
        if not isinstance(raw_key, str) or not isinstance(raw_name, str):
            continue
        destination_ip, destination_port = _parse_destination_key(raw_key)
        if destination_ip is None:
            continue
        entries.append(
            ServiceMapEntry(
                name=raw_name,
                destination_ip=destination_ip,
                destination_port=destination_port,
            ),
        )
    return entries


def _parse_object_entry(raw_entry: dict[Any, Any]) -> ServiceMapEntry:
    destination_ip = raw_entry.get("destination_ip")
    name = raw_entry.get("name")
    if not isinstance(destination_ip, str) or not isinstance(name, str):
        raise ValueError("Cada servicio requiere name y destination_ip")

    destination_port = raw_entry.get("destination_port")
    if destination_port is not None and not isinstance(destination_port, int):
        raise ValueError("destination_port debe ser numerico")

    destination_host = raw_entry.get("destination_host")
    if destination_host is not None and not isinstance(destination_host, str):
        raise ValueError("destination_host debe ser texto")

    return ServiceMapEntry(
        name=name,
        destination_ip=destination_ip,
        destination_port=destination_port,
        destination_host=destination_host,
    )


def _parse_destination_key(raw_key: str) -> tuple[str | None, int | None]:
    destination_ip, separator, raw_port = raw_key.partition(":")
    if not destination_ip:
        return None, None
    if separator == "" or raw_port == "*":
        return destination_ip, None
    return destination_ip, int(raw_port)
