"""Add collection run error message.

Revision ID: 006_add_collection_run_error_message
Revises: 005_add_collection_runs
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006_add_collection_run_error_message"
down_revision = "005_add_collection_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_runs", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("collection_runs", "error_message")
