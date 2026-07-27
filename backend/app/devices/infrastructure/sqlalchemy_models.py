from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.shared.database import Base


class DeviceModel(Base):
    __tablename__ = "devices"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    os_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[dict[str, str]] = mapped_column("metadata", JSON, nullable=False)


class AgentCredentialModel(Base):
    __tablename__ = "agent_credentials"

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    token_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
