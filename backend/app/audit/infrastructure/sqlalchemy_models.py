from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.shared.database import Base


class NetworkAuditEventModel(Base):
    __tablename__ = "network_audit_events"
    __table_args__ = (
        Index(
            "ix_network_audit_events_company_device_occurred",
            "company_id",
            "device_id",
            "occurred_at",
        ),
        Index(
            "ix_network_audit_events_company_link_occurred",
            "company_id",
            "company_device_link_id",
            "occurred_at",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    company_device_link_id: Mapped[str] = mapped_column(String(36), index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    os_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol: Mapped[str] = mapped_column(String(32), index=True)
    local_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    public_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    destination_host: Mapped[str | None] = mapped_column(String(255), index=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    destination_port: Mapped[int | None] = mapped_column(Integer, index=True)
    http_method: Mapped[str | None] = mapped_column(String(16))
    http_status_code: Mapped[int | None] = mapped_column(Integer)
    bytes_sent: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes_received: Mapped[int] = mapped_column(BigInteger, nullable=False)
    network_interface: Mapped[str | None] = mapped_column(String(128))
    mac_address: Mapped[str | None] = mapped_column(String(32))
    local_username: Mapped[str | None] = mapped_column(String(255), index=True)
    process_id: Mapped[int | None] = mapped_column(Integer)
    process_name: Mapped[str | None] = mapped_column(String(255), index=True)
    process_executable: Mapped[str | None] = mapped_column(String(1024))
    service_name: Mapped[str | None] = mapped_column(String(255), index=True)
    request_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    response_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentLifecycleEventModel(Base):
    __tablename__ = "agent_lifecycle_events"
    __table_args__ = (
        Index(
            "ix_agent_lifecycle_events_company_device_occurred",
            "company_id",
            "device_id",
            "occurred_at",
        ),
        Index(
            "ix_agent_lifecycle_events_company_link_occurred",
            "company_id",
            "company_device_link_id",
            "occurred_at",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    company_id: Mapped[str] = mapped_column(String(36), index=True)
    company_device_link_id: Mapped[str] = mapped_column(String(36), index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    local_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    public_ip: Mapped[str | None] = mapped_column(String(45), index=True)
    reason: Mapped[str | None] = mapped_column(String(500))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downtime_seconds: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
