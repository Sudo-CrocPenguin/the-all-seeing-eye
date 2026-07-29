from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.shared.database import Base


class CompanyModel(Base):
    __tablename__ = "companies"

    company_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)


class EnrollmentCodeModel(Base):
    __tablename__ = "company_enrollment_codes"

    enrollment_code_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    code_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnrollmentRequestModel(Base):
    __tablename__ = "company_enrollment_requests"
    __table_args__ = (
        Index(
            "uq_company_enrollment_requests_pending_device",
            "company_id",
            "device_id",
            unique=True,
            sqlite_where=text("status = 'PENDING'"),
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    enrollment_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewed_by_auditor_session_id: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    device_fingerprint_snapshot: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)


class CompanyDeviceLinkModel(Base):
    __tablename__ = "company_device_links"
    __table_args__ = (
        Index(
            "uq_company_device_links_active_device",
            "company_id",
            "device_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE' AND revoked_at IS NULL"),
            postgresql_where=text("status = 'ACTIVE' AND revoked_at IS NULL"),
        ),
    )

    company_device_link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_device: Mapped[bool] = mapped_column(Boolean, nullable=False)
    revoked_by_auditor_session_id: Mapped[str | None] = mapped_column(String(36))


class AuditorAccessRequestModel(Base):
    __tablename__ = "auditor_access_requests"

    auditor_access_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    otp_salt: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auditor_session_id: Mapped[str | None] = mapped_column(String(36))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class AuditorSessionModel(Base):
    __tablename__ = "auditor_sessions"

    auditor_session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditorOtpEventModel(Base):
    __tablename__ = "auditor_otp_events"
    __table_args__ = (
        Index(
            "ix_auditor_otp_events_company_type_occurred",
            "company_id",
            "event_type",
            "occurred_at",
        ),
        Index(
            "ix_auditor_otp_events_device_type_occurred",
            "device_id",
            "event_type",
            "occurred_at",
        ),
        Index(
            "ix_auditor_otp_events_ip_type_occurred",
            "client_ip",
            "event_type",
            "occurred_at",
        ),
    )

    otp_event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), index=True)
    auditor_access_request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
