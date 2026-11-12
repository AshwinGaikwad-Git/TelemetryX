"""Service for running ML experiments, fitting models, and registering artifacts."""

import subprocess
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ExperimentCreate
from app.core.config import get_settings
from app.db.models import (
    DatasetVersion,
    EvaluationRun,
    Experiment,
    ModelVersion,
)
from app.ml.evaluator import evaluate_predictions
from app.ml.models import GradientBoostingRULModel, NaiveBaselineModel
from app.pipelines.features import LeakFreePreprocessor, calculate_capped_rul
from app.services.dataset_service import (
    DatasetService,
    persist_feature_snapshot,
    training_dataframe,
)


def get_models_dir() -> Path:
    directory = get_settings().model_storage_path
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class ExperimentService:
    @staticmethod
    def list_experiments(db: Session) -> list[dict[str, Any]]:
        stmt = select(Experiment).order_by(Experiment.created_at.desc())
        experiments = db.scalars(stmt).all()

        results = []
        for exp in experiments:
            mv = exp.models[0] if exp.models else None
            results.append(
                {
                    "id": exp.id,
                    "name": exp.name,
                    "dataset_version_id": exp.dataset_version_id,
                    "algorithm": exp.algorithm,
                    "status": exp.status,
                    "random_seed": exp.random_seed,
                    "created_at": exp.created_at,
                    "model_version_id": mv.id if mv else None,
                    "metrics": mv.metrics if mv else None,
                }
            )
        return results

    @staticmethod
    def list_models(db: Session) -> list[dict[str, Any]]:
        stmt = select(ModelVersion).order_by(ModelVersion.created_at.desc())
        models = db.scalars(stmt).all()

        results = []
        for m in models:
            results.append(
                {
                    "id": m.id,
                    "experiment_id": m.experiment_id,
                    "dataset_version_id": m.experiment.dataset_version_id,
                    "version": m.version,
                    "artifact_uri": m.artifact_uri,
                    "metrics": m.metrics,
                    "status": m.status,
                    "created_at": m.created_at,
                }
            )
        return results

    @staticmethod
    def run_training_experiment(db: Session, req: ExperimentCreate) -> dict[str, Any]:
        """Trains a gradient boosting RUL model from an immutable prepared feature set."""
        ds = db.get(DatasetVersion, req.dataset_version_id)
        if not ds:
            raise ValueError(f"Dataset {req.dataset_version_id} not found")

        DatasetService.prepare_feature_set(db, ds.id)
        df = training_dataframe(db, ds.id)
        units = np.sort(df["unit_number"].unique())
        if len(units) < 2:
            raise ValueError("At least two training engines are required for group validation")
        rng = np.random.default_rng(req.random_seed)
        val_size = min(len(units) - 1, max(1, int(len(units) * req.validation_fraction)))
        shuffled_units = rng.permutation(units)
        val_units = set(shuffled_units[:val_size])
        train_units = set(shuffled_units[val_size:])
        train_df = df[df["unit_number"].isin(train_units)].copy()
        val_df = df[df["unit_number"].isin(val_units)].copy()
        # Split raw engines BEFORE learning sensor masks or scaler statistics.
        preprocessor = LeakFreePreprocessor(rul_cap=req.rul_cap)
        X_train_df, y_train_series, fitted_manifest = preprocessor.fit_transform(train_df)
        X_val_df = preprocessor.transform(val_df)
        y_val_series = calculate_capped_rul(val_df, rul_cap=req.rul_cap)
        feature_cols = fitted_manifest.feature_names
        X_train = X_train_df[feature_cols].to_numpy()
        y_train = y_train_series.to_numpy()
        X_val = X_val_df[feature_cols].to_numpy()
        y_val = y_val_series.to_numpy()
        val_unit_ids = X_val_df["unit_number"].tolist()
        snapshot = pd.concat([X_train_df, X_val_df]).sort_index()
        targets = pd.concat([y_train_series, y_val_series]).sort_index()
        manifest_data = fitted_manifest.to_dict()
        manifest_data["extra"] = {
            "train_units": sorted(int(u) for u in train_units),
            "val_units": sorted(int(u) for u in val_units),
            "dataset_checksum": ds.checksum_sha256,
        }
        fitted_manifest.extra = manifest_data["extra"]
        fs = persist_feature_snapshot(
            db, ds.id, "experiment-snapshot", snapshot, targets, manifest_data
        )

        # 4. Train Model
        hp = req.hyperparameters
        model: GradientBoostingRULModel | NaiveBaselineModel = GradientBoostingRULModel(
            learning_rate=float(hp.get("learning_rate", 0.08)),
            max_iter=int(hp.get("max_iter", 120)),
            max_depth=int(hp.get("max_depth", 6)),
            random_state=req.random_seed,
        )
        if req.algorithm == "naive":
            model = NaiveBaselineModel()
        model.fit(X_train, y_train, manifest=fitted_manifest)

        # 5. Evaluate on Validation Group
        val_preds, lower, upper = model.predict(X_val)
        val_report = evaluate_predictions(
            y_val,
            val_preds,
            unit_ids=val_unit_ids,
            lower_bounds=lower,
            upper_bounds=upper,
        )

        # 6. Persist Model Artifact
        models_dir = get_models_dir()
        version_str = f"{req.algorithm}-v{uuid.uuid4().hex[:8]}"
        artifact_path = models_dir / f"{version_str}.joblib"
        model.save(artifact_path)

        # 7. Record Experiment & Model Version
        exp = Experiment(
            name=req.name,
            dataset_version_id=ds.id,
            feature_set_id=fs.id,
            algorithm=req.algorithm,
            hyperparameters=req.hyperparameters,
            split_definition={
                "strategy": "group_by_engine",
                "validation_fraction": req.validation_fraction,
                "train_units": [int(u) for u in train_units],
                "val_units": [int(u) for u in val_units],
            },
            random_seed=req.random_seed,
            status="completed",
        )
        db.add(exp)
        db.flush()

        mv = ModelVersion(
            experiment_id=exp.id,
            version=version_str,
            artifact_uri=str(artifact_path),
            feature_manifest=fitted_manifest.to_dict(),
            training_data_range={
                "dataset_checksum": ds.checksum_sha256,
                "feature_snapshot_sha256": fs.parameters["snapshot_sha256"],
                "code_revision": code_revision(),
            },
            metrics=val_report.to_dict(),
            status="active",
        )
        db.add(mv)
        db.flush()

        eval_run = EvaluationRun(
            model_version_id=mv.id,
            dataset_version_id=ds.id,
            evaluation_role="validation",
            metrics=val_report.to_dict(),
        )
        db.add(eval_run)
        db.commit()

        return {
            "experiment_id": exp.id,
            "model_version_id": mv.id,
            "version": mv.version,
            "metrics": val_report.to_dict(),
            "status": "completed",
        }


def code_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
