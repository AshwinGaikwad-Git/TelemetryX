"""Create the foundation metadata table.

Revision ID: 20260901_0001
Revises:
Create Date: 2026-09-01 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260901_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_metadata",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key", name="pk_system_metadata"),
    )


def downgrade() -> None:
    op.drop_table("system_metadata")
