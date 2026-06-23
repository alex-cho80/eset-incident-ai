"""Add notification deliveries.

Revision ID: 003_add_notification_deliveries
Revises: 002_add_vector_index
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_add_notification_deliveries"
down_revision = "002_add_vector_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("delivery_status", sa.String(30), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_deliveries")
