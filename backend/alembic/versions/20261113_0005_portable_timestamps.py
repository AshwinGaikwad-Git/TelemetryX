"""Repair industrial timestamp defaults on existing migrated SQLite databases."""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0005"
down_revision = "20261113_0004"
branch_labels = None
depends_on = None

TABLES = (
    "industrial_companies", "industrial_users", "industrial_audit_events",
    "industrial_ingestion_keys", "industrial_machines", "industrial_alerts",
    "industrial_work_orders",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # SQLite rebuilds tables to change a default. Disable FK checks outside a
        # transaction while replacing parents, then verify all references before exit.
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys=OFF")
            try:
                for table in TABLES:
                    with op.batch_alter_table(table, recreate="always") as batch:
                        batch.alter_column("created_at", existing_type=sa.DateTime(timezone=True),
                                           server_default=sa.text("CURRENT_TIMESTAMP"))
                if op.get_bind().exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                    raise RuntimeError("Foreign-key check failed after timestamp migration")
            finally:
                op.execute("PRAGMA foreign_keys=ON")
    else:
        for table in TABLES:
            op.alter_column(table, "created_at", existing_type=sa.DateTime(timezone=True),
                            server_default=sa.text("CURRENT_TIMESTAMP"))


def downgrade() -> None:
    # These portable defaults remain compatible with revision 0004. Do not
    # reintroduce an invalid now() default when moving back to the older schema.
    pass
