"""Add collection runs.

Revision ID: 005_add_collection_runs
Revises: 004_add_pending_approvals
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "005_add_collection_runs"
down_revision = "004_add_pending_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("collected_count", sa.Integer(), nullable=False),
        sa.Column("notified_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_skipped_count", sa.Integer(), nullable=False),
        sa.Column("pending_approval_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("observed_keys", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("collection_runs")
