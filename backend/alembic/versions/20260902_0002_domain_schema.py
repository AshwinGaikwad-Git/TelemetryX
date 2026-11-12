"""Create domain tables for datasets, engines, features, experiments, models, and predictions.

Revision ID: 20260902_0002
Revises: 20260901_0001
Create Date: 2026-09-02 00:00:00
"""

import sqlalchemy as sa

from alembic import op

revision = "20260902_0002"
down_revision = "20260901_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. dataset_versions
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_code", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_uri", sa.String(length=500), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("parser_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("preprocessing_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="imported", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_versions"),
    )
    op.create_index("ix_dataset_versions_dataset_code", "dataset_versions", ["dataset_code"])
    op.create_index("ix_dataset_versions_status", "dataset_versions", ["status"])

    # 2. dataset_files
    op.create_table(
        "dataset_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("file_role", sa.String(length=50), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_uri", sa.String(length=500), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engine_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="validated", nullable=False),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], name="fk_dataset_files_version_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_files"),
        sa.UniqueConstraint("dataset_version_id", "file_role", "checksum_sha256", name="uq_dataset_file_checksum"),
    )
    op.create_index("ix_dataset_files_dataset_version_id", "dataset_files", ["dataset_version_id"])

    # 3. engine_runs
    op.create_table(
        "engine_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("file_role", sa.String(length=50), nullable=False),
        sa.Column("unit_number", sa.Integer(), nullable=False),
        sa.Column("max_cycle", sa.Integer(), nullable=False),
        sa.Column("ground_truth_rul", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], name="fk_engine_runs_version_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_engine_runs"),
        sa.UniqueConstraint("dataset_version_id", "file_role", "unit_number", name="uq_engine_run_unit"),
    )
    op.create_index("ix_engine_runs_dataset_version_id", "engine_runs", ["dataset_version_id"])
    op.create_index("ix_engine_runs_unit_number", "engine_runs", ["unit_number"])

    # 4. engine_cycles
    op.create_table(
        "engine_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("engine_run_id", sa.Uuid(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("operational_settings", sa.JSON(), nullable=False),
        sa.Column("sensor_values", sa.JSON(), nullable=False),
        sa.Column("quality_flag", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["engine_run_id"], ["engine_runs.id"], name="fk_engine_cycles_run_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_engine_cycles"),
        sa.UniqueConstraint("engine_run_id", "cycle", name="uq_engine_cycle"),
    )
    op.create_index("idx_engine_cycle_run_cycle", "engine_cycles", ["engine_run_id", "cycle"])

    # 5. feature_sets
    op.create_table(
        "feature_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("feature_version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("feature_manifest_uri", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], name="fk_feature_sets_version_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feature_sets"),
    )
    op.create_index("ix_feature_sets_dataset_version_id", "feature_sets", ["dataset_version_id"])

    # 6. cycle_features
    op.create_table(
        "cycle_features",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feature_set_id", sa.Uuid(), nullable=False),
        sa.Column("engine_run_id", sa.Uuid(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("rul_target", sa.Float(), nullable=True),
        sa.Column("sequence_eligible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["feature_set_id"], ["feature_sets.id"], name="fk_cycle_features_set_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["engine_run_id"], ["engine_runs.id"], name="fk_cycle_features_run_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_cycle_features"),
        sa.UniqueConstraint("feature_set_id", "engine_run_id", "cycle", name="uq_cycle_features"),
    )

    # 7. experiments
    op.create_table(
        "experiments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("feature_set_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm", sa.String(length=100), nullable=False),
        sa.Column("hyperparameters", sa.JSON(), nullable=False),
        sa.Column("split_definition", sa.JSON(), nullable=False),
        sa.Column("random_seed", sa.Integer(), server_default="42", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], name="fk_experiments_dataset_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["feature_set_id"], ["feature_sets.id"], name="fk_experiments_feature_set_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_experiments"),
    )

    # 8. model_versions
    op.create_table(
        "model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("artifact_uri", sa.String(length=500), nullable=False),
        sa.Column("feature_manifest", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("training_data_range", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], name="fk_model_versions_exp_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_model_versions"),
    )

    # 9. evaluation_runs
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_role", sa.String(length=50), server_default="test", nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("per_unit_results_uri", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["model_versions.id"], name="fk_evaluation_runs_model_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"], ["dataset_versions.id"], name="fk_evaluation_runs_dataset_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_runs"),
    )

    # 10. rul_predictions
    op.create_table(
        "rul_predictions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("engine_run_id", sa.Uuid(), nullable=False),
        sa.Column("cycle", sa.Integer(), nullable=False),
        sa.Column("predicted_rul", sa.Float(), nullable=False),
        sa.Column("lower_bound", sa.Float(), nullable=False),
        sa.Column("upper_bound", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["model_version_id"], ["model_versions.id"], name="fk_predictions_model_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["engine_run_id"], ["engine_runs.id"], name="fk_predictions_run_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_rul_predictions"),
        sa.UniqueConstraint("model_version_id", "engine_run_id", "cycle", name="uq_rul_prediction_cycle"),
    )
    op.create_index("idx_predictions_run_cycle", "rul_predictions", ["engine_run_id", "cycle"])
    op.create_index("ix_rul_predictions_risk_level", "rul_predictions", ["risk_level"])

    # 11. prediction_explanations
    op.create_table(
        "prediction_explanations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prediction_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=50), server_default="shap_tree", nullable=False),
        sa.Column("baseline", sa.JSON(), nullable=True),
        sa.Column("top_contributors", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prediction_id"], ["rul_predictions.id"], name="fk_explanations_pred_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_prediction_explanations"),
        sa.UniqueConstraint("prediction_id", name="uq_prediction_explanation_pred_id"),
    )

    # 12. maintenance_recommendations
    op.create_table(
        "maintenance_recommendations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prediction_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_type", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["prediction_id"], ["rul_predictions.id"], name="fk_recommendations_pred_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_maintenance_recommendations"),
        sa.UniqueConstraint("prediction_id", name="uq_maintenance_recommendation_pred_id"),
    )

    # 13. job_runs
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_job_runs_idempotency_key"),
    )
    op.create_index("ix_job_runs_job_type", "job_runs", ["job_type"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("maintenance_recommendations")
    op.drop_table("prediction_explanations")
    op.drop_table("rul_predictions")
    op.drop_table("evaluation_runs")
    op.drop_table("model_versions")
    op.drop_table("experiments")
    op.drop_table("cycle_features")
    op.drop_table("feature_sets")
    op.drop_table("engine_cycles")
    op.drop_table("engine_runs")
    op.drop_table("dataset_files")
    op.drop_table("dataset_versions")
