"""Company-scoped equipment models and immutable prediction evidence."""

import sqlalchemy as sa

from alembic import op

revision = "20261113_0006"
down_revision = "20261113_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industrial_equipment_models",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "company_id", sa.Uuid(), sa.ForeignKey("industrial_companies.id"), nullable=False
        ),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("feature_schema", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "company_id", "machine_id"),
        sa.ForeignKeyConstraint(
            ["machine_id", "company_id"],
            ["industrial_machines.id", "industrial_machines.company_id"],
        ),
    )
    op.create_table(
        "industrial_equipment_predictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "company_id", sa.Uuid(), sa.ForeignKey("industrial_companies.id"), nullable=False
        ),
        sa.Column("machine_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("remaining_hours", sa.Float(), nullable=False),
        sa.Column("lower_hours", sa.Float(), nullable=False),
        sa.Column("upper_hours", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["model_id", "company_id", "machine_id"],
            [
                "industrial_equipment_models.id",
                "industrial_equipment_models.company_id",
                "industrial_equipment_models.machine_id",
            ],
        ),
    )
    for table in ("industrial_equipment_models", "industrial_equipment_predictions"):
        for column in ("company_id", "machine_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    op.drop_table("industrial_equipment_predictions")
    op.drop_table("industrial_equipment_models")
