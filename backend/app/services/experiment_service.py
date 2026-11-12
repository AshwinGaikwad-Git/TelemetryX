"""Service for running ML experiments, fitting models, and registering artifacts."""

import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ExperimentCreate
from app.db.models import (
    DatasetVersion,
    EngineRun,
    EvaluationRun,
    Experiment,
    FeatureSet,
    ModelVersion,
)
from app.ml.evaluator import evaluate_predictions
from app.ml.models import GradientBoostingRULModel
from app.pipelines.constants import SETTINGS_COLUMNS
from app.pipelines.features import FeatureManifest, LeakFreePreprocessor


def get_models_dir() -> Path:
    candidates = [
        Path("models"),
        Path("../models"),
        Path(__file__).resolve().parent.parent.parent.parent / "models",
    ]
    for c in candidates:
        if c.exists():
            return c
    m = Path("models")
    m.mkdir(parents=True, exist_ok=True)
    return m


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

        # 1. Ensure FeatureSet exists
        stmt_fs = (
            select(FeatureSet)
            .where(FeatureSet.dataset_version_id == ds.id)
            .order_by(FeatureSet.created_at.desc())
        )
        fs = db.scalars(stmt_fs).first()
        if not fs:
            from app.services.dataset_service import DatasetService

            fs = DatasetService.prepare_feature_set(db, ds.id, rul_cap=req.rul_cap)

        manifest = FeatureManifest.from_dict(fs.parameters)

        # 2. Reconstruct training telemetry DataFrame
        runs = db.scalars(
            select(EngineRun).where(
                EngineRun.dataset_version_id == ds.id,
                EngineRun.file_role == "train",
            )
        ).all()
        if not runs:
            raise ValueError("No training runs found in dataset")

        rows = []
        for r in runs:
            for c in r.cycles:
                row_dict: dict[str, Any] = {
                    "unit_number": r.unit_number,
                    "cycle": c.cycle,
                }
                for i, setting in enumerate(SETTINGS_COLUMNS):
                    row_dict[setting] = c.operational_settings[i]
                for s, val in c.sensor_values.items():
                    row_dict[s] = val
                rows.append(row_dict)

        df = pd.DataFrame(rows)

        # 3. Fit-transform features and capped targets
        preprocessor = LeakFreePreprocessor(rul_cap=manifest.rul_cap)
        X_df, y_series, fitted_manifest = preprocessor.fit_transform(df)

        feature_cols = fitted_manifest.feature_names
        units = X_df["unit_number"].unique()

        # Engine-level train/validation split (NO cross-engine leakage)
        rng = np.random.default_rng(req.random_seed)
        val_size = max(1, int(len(units) * req.validation_fraction))
        shuffled_units = rng.permutation(units)
        val_units = set(shuffled_units[:val_size])
        train_units = set(shuffled_units[val_size:])

        train_mask = X_df["unit_number"].isin(train_units)
        val_mask = X_df["unit_number"].isin(val_units)

        X_train = X_df.loc[train_mask, feature_cols].to_numpy()
        y_train = y_series.loc[train_mask].to_numpy()

        X_val = X_df.loc[val_mask, feature_cols].to_numpy()
        y_val = y_series.loc[val_mask].to_numpy()
        val_unit_ids = X_df.loc[val_mask, "unit_number"].tolist()

        # 4. Train Model
        hp = req.hyperparameters
        model = GradientBoostingRULModel(
            learning_rate=float(hp.get("learning_rate", 0.08)),
            max_iter=int(hp.get("max_iter", 120)),
            max_depth=int(hp.get("max_depth", 6)),
            random_state=req.random_seed,
        )
        model.fit(X_train, y_train, manifest=fitted_manifest)

        # 5. Evaluate on Validation Group
        val_preds, _, _ = model.predict(X_val)
        val_report = evaluate_predictions(y_val, val_preds, unit_ids=val_unit_ids)

        # 6. Persist Model Artifact
        models_dir = get_models_dir()
        version_str = f"gbr-v{uuid.uuid4().hex[:8]}"
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
