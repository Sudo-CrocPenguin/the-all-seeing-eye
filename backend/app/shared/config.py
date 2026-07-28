from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_ENVS = {"local", "test", "development"}
_MIN_SHARED_SECRET_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "The All Seeing Eye"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://audit:audit@localhost:5432/the_all_seeing_eye"
    persistence_backend: Literal["memory", "sqlalchemy"] = "sqlalchemy"
    api_docs_enabled: bool = True
    health_require_current_migration: bool = False
    agent_heartbeat_timeout_seconds: int = 180
    missed_heartbeat_scheduler_enabled: bool = False
    missed_heartbeat_scheduler_interval_seconds: int = 60
    agent_token_header: str = "X-Agent-Token"
    auditor_token: str | None = None
    auditor_token_header: str = "X-Auditor-Token"
    provisioning_token: str | None = None
    provisioning_token_header: str = "X-Provisioning-Token"
    trusted_proxy_ips: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def validate_non_local_security(self) -> "Settings":
        if self.app_env.lower() in _LOCAL_ENVS:
            return self

        _require_strong_shared_secret("AUDITOR_TOKEN", self.auditor_token)
        _require_strong_shared_secret("PROVISIONING_TOKEN", self.provisioning_token)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _require_strong_shared_secret(name: str, value: str | None) -> None:
    if value is None or len(value.strip()) < _MIN_SHARED_SECRET_LENGTH:
        raise ValueError(
            f"{name} debe tener al menos {_MIN_SHARED_SECRET_LENGTH} caracteres "
            "en entornos no locales",
        )
