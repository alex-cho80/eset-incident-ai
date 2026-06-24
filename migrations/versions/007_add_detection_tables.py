"""Add detection tables.

Revision ID: 007_add_detection_tables
Revises: 006_add_collection_run_error_message
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_add_detection_tables"
down_revision = "006_add_collection_run_error_message"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_detection_approvals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("detection_id", sa.String(128), nullable=False, unique=True),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "detection_collection_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("collected_count", sa.Integer(), nullable=False),
        sa.Column("notified_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_skipped_count", sa.Integer(), nullable=False),
        sa.Column("pending_approval_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("observed_keys", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_page_token", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("detection_collection_runs")
    op.drop_table("pending_detection_approvals")
