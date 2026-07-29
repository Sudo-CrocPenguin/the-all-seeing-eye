"""crear tablas de autenticacion multiempresa

Revision ID: 202607290001
Revises: 202607280002
Create Date: 2026-07-29 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607290001"
down_revision: str | None = "202607280002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("company_id"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_status", "companies", ["status"])

    op.create_table(
        "company_enrollment_codes",
        sa.Column("enrollment_code_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("code_digest", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("code_salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("enrollment_code_id"),
        sa.UniqueConstraint("code_digest"),
    )
    op.create_index(
        "ix_company_enrollment_codes_code_digest",
        "company_enrollment_codes",
        ["code_digest"],
    )
    op.create_index(
        "ix_company_enrollment_codes_company_id",
        "company_enrollment_codes",
        ["company_id"],
    )

    op.create_table(
        "company_enrollment_requests",
        sa.Column("enrollment_request_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewed_by_auditor_session_id", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_fingerprint_snapshot", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("enrollment_request_id"),
    )
    op.create_index(
        "ix_company_enrollment_requests_company_id",
        "company_enrollment_requests",
        ["company_id"],
    )
    op.create_index(
        "ix_company_enrollment_requests_device_id",
        "company_enrollment_requests",
        ["device_id"],
    )
    op.create_index(
        "ix_company_enrollment_requests_status",
        "company_enrollment_requests",
        ["status"],
    )

    op.create_table(
        "company_device_links",
        sa.Column("company_device_link_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_device", sa.Boolean(), nullable=False),
        sa.Column("revoked_by_auditor_session_id", sa.String(length=36), nullable=True),
        sa.PrimaryKeyConstraint("company_device_link_id"),
    )
    op.create_index("ix_company_device_links_company_id", "company_device_links", ["company_id"])
    op.create_index("ix_company_device_links_device_id", "company_device_links", ["device_id"])
    op.create_index("ix_company_device_links_status", "company_device_links", ["status"])

    op.create_table(
        "auditor_access_requests",
        sa.Column("auditor_access_request_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("otp_salt", sa.String(length=64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auditor_session_id", sa.String(length=36), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("auditor_access_request_id"),
    )
    op.create_index(
        "ix_auditor_access_requests_company_id",
        "auditor_access_requests",
        ["company_id"],
    )
    op.create_index(
        "ix_auditor_access_requests_device_id",
        "auditor_access_requests",
        ["device_id"],
    )
    op.create_index(
        "ix_auditor_access_requests_status",
        "auditor_access_requests",
        ["status"],
    )

    op.create_table(
        "auditor_sessions",
        sa.Column("auditor_session_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("auditor_session_id"),
    )
    op.create_index("ix_auditor_sessions_company_id", "auditor_sessions", ["company_id"])
    op.create_index("ix_auditor_sessions_device_id", "auditor_sessions", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_auditor_sessions_device_id", table_name="auditor_sessions")
    op.drop_index("ix_auditor_sessions_company_id", table_name="auditor_sessions")
    op.drop_table("auditor_sessions")

    op.drop_index("ix_auditor_access_requests_status", table_name="auditor_access_requests")
    op.drop_index("ix_auditor_access_requests_device_id", table_name="auditor_access_requests")
    op.drop_index("ix_auditor_access_requests_company_id", table_name="auditor_access_requests")
    op.drop_table("auditor_access_requests")

    op.drop_index("ix_company_device_links_status", table_name="company_device_links")
    op.drop_index("ix_company_device_links_device_id", table_name="company_device_links")
    op.drop_index("ix_company_device_links_company_id", table_name="company_device_links")
    op.drop_table("company_device_links")

    op.drop_index(
        "ix_company_enrollment_requests_status",
        table_name="company_enrollment_requests",
    )
    op.drop_index(
        "ix_company_enrollment_requests_device_id",
        table_name="company_enrollment_requests",
    )
    op.drop_index(
        "ix_company_enrollment_requests_company_id",
        table_name="company_enrollment_requests",
    )
    op.drop_table("company_enrollment_requests")

    op.drop_index(
        "ix_company_enrollment_codes_company_id",
        table_name="company_enrollment_codes",
    )
    op.drop_index(
        "ix_company_enrollment_codes_code_digest",
        table_name="company_enrollment_codes",
    )
    op.drop_table("company_enrollment_codes")

    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
