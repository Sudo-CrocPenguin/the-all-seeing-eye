import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class AgentStateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LinkedCompanyState:
    company_id: str
    company_device_link_id: str
    company_name: str
    status: str = "ACTIVE"
    linked_at: str | None = None
    revoked_at: str | None = None

    @classmethod
    def from_json(cls, raw_value: dict[str, Any]) -> "LinkedCompanyState":
        return cls(
            company_id=_required_text(raw_value, "company_id"),
            company_device_link_id=_required_text(raw_value, "company_device_link_id"),
            company_name=_required_text(raw_value, "company_name"),
            status=_optional_text(raw_value, "status") or "ACTIVE",
            linked_at=_optional_text(raw_value, "linked_at"),
            revoked_at=_optional_text(raw_value, "revoked_at"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "company_device_link_id": self.company_device_link_id,
            "company_name": self.company_name,
            "status": self.status,
            "linked_at": self.linked_at,
            "revoked_at": self.revoked_at,
        }

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE" and self.revoked_at is None


@dataclass(frozen=True, slots=True)
class AgentState:
    device_id: str | None = None
    recording_enabled: bool = False
    active_company_id: str | None = None
    active_company_device_link_id: str | None = None
    linked_companies: tuple[LinkedCompanyState, ...] = field(default_factory=tuple)

    @classmethod
    def from_json(cls, raw_value: dict[str, Any]) -> "AgentState":
        raw_linked_companies = raw_value.get("linked_companies", [])
        if not isinstance(raw_linked_companies, list):
            raise AgentStateError("linked_companies debe ser una lista")

        return cls(
            device_id=_optional_text(raw_value, "device_id"),
            recording_enabled=_optional_bool(raw_value, "recording_enabled", False),
            active_company_id=_optional_text(raw_value, "active_company_id"),
            active_company_device_link_id=_optional_text(
                raw_value,
                "active_company_device_link_id",
            ),
            linked_companies=tuple(
                LinkedCompanyState.from_json(_require_object(item, "linked_companies"))
                for item in raw_linked_companies
            ),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "recording_enabled": self.recording_enabled,
            "active_company_id": self.active_company_id,
            "active_company_device_link_id": self.active_company_device_link_id,
            "linked_companies": [company.to_json() for company in self.linked_companies],
        }

    @property
    def active_company(self) -> LinkedCompanyState | None:
        if self.active_company_id is None or self.active_company_device_link_id is None:
            return None
        for company in self.linked_companies:
            if (
                company.company_id == self.active_company_id
                and company.company_device_link_id == self.active_company_device_link_id
            ):
                return company
        return None

    def with_device_id(self, device_id: str) -> "AgentState":
        return AgentState(
            device_id=device_id,
            recording_enabled=self.recording_enabled,
            active_company_id=self.active_company_id,
            active_company_device_link_id=self.active_company_device_link_id,
            linked_companies=self.linked_companies,
        )

    def with_recording_enabled(self, recording_enabled: bool) -> "AgentState":
        return AgentState(
            device_id=self.device_id,
            recording_enabled=recording_enabled,
            active_company_id=self.active_company_id,
            active_company_device_link_id=self.active_company_device_link_id,
            linked_companies=self.linked_companies,
        )

    def upsert_link(self, link: LinkedCompanyState) -> "AgentState":
        linked_companies = [
            existing
            for existing in self.linked_companies
            if existing.company_device_link_id != link.company_device_link_id
            and existing.company_id != link.company_id
        ]
        linked_companies.append(link)
        linked_companies.sort(key=lambda item: item.company_name.lower())
        return AgentState(
            device_id=self.device_id,
            recording_enabled=self.recording_enabled,
            active_company_id=self.active_company_id,
            active_company_device_link_id=self.active_company_device_link_id,
            linked_companies=tuple(linked_companies),
        )

    def select_company(self, company_id: str) -> "AgentState":
        selected_company = self.find_active_company(company_id)
        if selected_company is None:
            raise AgentStateError("La empresa no esta vinculada o no esta activa")
        return AgentState(
            device_id=self.device_id,
            recording_enabled=self.recording_enabled,
            active_company_id=selected_company.company_id,
            active_company_device_link_id=selected_company.company_device_link_id,
            linked_companies=self.linked_companies,
        )

    def remove_company(self, company_id: str) -> "AgentState":
        linked_companies = tuple(
            company for company in self.linked_companies if company.company_id != company_id
        )
        active_company_id = self.active_company_id
        active_company_device_link_id = self.active_company_device_link_id
        if self.active_company_id == company_id:
            active_company_id = None
            active_company_device_link_id = None
        return AgentState(
            device_id=self.device_id,
            recording_enabled=self.recording_enabled,
            active_company_id=active_company_id,
            active_company_device_link_id=active_company_device_link_id,
            linked_companies=linked_companies,
        )

    def find_active_company(self, company_id: str) -> LinkedCompanyState | None:
        for company in self.linked_companies:
            if company.company_id == company_id and company.is_active:
                return company
        return None


class JsonAgentStateStore:
    def __init__(self, state_file: Path) -> None:
        self._state_file = state_file

    @property
    def state_file(self) -> Path:
        return self._state_file

    def load(self) -> AgentState:
        if not self._state_file.exists():
            return AgentState()
        try:
            raw_value = json.loads(self._state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentStateError(f"Estado local invalido en {self._state_file}") from exc
        if not isinstance(raw_value, dict):
            raise AgentStateError("El estado local debe ser un objeto JSON")
        return AgentState.from_json(raw_value)

    def save(self, state: AgentState) -> AgentState:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self._state_file.with_suffix(f"{self._state_file.suffix}.tmp")
        temporary_file.write_text(
            json.dumps(state.to_json(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary_file.replace(self._state_file)
        return state


def _required_text(raw_value: dict[str, Any], field_name: str) -> str:
    value = _optional_text(raw_value, field_name)
    if value is None:
        raise AgentStateError(f"{field_name} es obligatorio")
    return value


def _optional_text(raw_value: dict[str, Any], field_name: str) -> str | None:
    value = raw_value.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AgentStateError(f"{field_name} debe ser texto")
    normalized = value.strip()
    return normalized or None


def _optional_bool(raw_value: dict[str, Any], field_name: str, default: bool) -> bool:
    value = raw_value.get(field_name, default)
    if not isinstance(value, bool):
        raise AgentStateError(f"{field_name} debe ser booleano")
    return value


def _require_object(raw_value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(raw_value, dict):
        raise AgentStateError(f"{field_name} debe contener objetos JSON")
    return raw_value
