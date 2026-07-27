from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "The All Seeing Eye"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://audit:audit@localhost:5432/the_all_seeing_eye"
    persistence_backend: Literal["memory", "sqlalchemy"] = "sqlalchemy"
    agent_heartbeat_timeout_seconds: int = 180
    agent_token_header: str = "X-Agent-Token"
    provisioning_token: str | None = None
    provisioning_token_header: str = "X-Provisioning-Token"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
