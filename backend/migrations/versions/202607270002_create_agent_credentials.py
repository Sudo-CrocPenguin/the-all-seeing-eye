"""crear credenciales de agente

Revision ID: 202607270002
Revises: 202607270001
Create Date: 2026-07-27 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607270002"
down_revision: str | None = "202607270001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_credentials",
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("token_salt", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("device_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_credentials")
