"""Persist background job inputs and results.

Revision ID: 20261113_0003
Revises: 20260902_0002
"""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0003"
down_revision = "20260902_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_runs", sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("job_runs", sa.Column("result", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_runs", "result")
    op.drop_column("job_runs", "payload")
