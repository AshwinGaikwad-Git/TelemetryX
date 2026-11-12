"""Service for managing C-MAPSS dataset versions, raw file ingestion, and validation."""

import json
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DatasetFile, DatasetVersion, EngineCycle, EngineRun, FeatureSet
from app.pipelines.constants import SENSOR_COLUMNS, SETTINGS_COLUMNS
from app.pipelines.features import LeakFreePreprocessor
from app.pipelines.parser import calculate_sha256, parse_file
from app.pipelines.validator import validate_rul_array, validate_telemetry_dataframe


def get_data_dir() -> Path:
    candidates = [
        Path("data"),
        Path("../data"),
        Path(__file__).resolve().parent.parent.parent.parent / "data",
    ]
    for c in candidates:
        if c.exists() and (c / "samples").exists():
            return c
    for c in candidates:
        if c.exists():
            return c
    return Path("data")


class DatasetService:
    @staticmethod
    def list_datasets(db: Session) -> list[dict[str, Any]]:
        stmt = select(DatasetVersion).order_by(DatasetVersion.created_at.desc())
        datasets = db.scalars(stmt).all()

        results = []
        for ds in datasets:
            runs = ds.engine_runs
            train_count = sum(1 for r in runs if r.file_role == "train")
            test_count = sum(1 for r in runs if r.file_role == "test")
            has_rul = any(r.ground_truth_rul is not None for r in runs if r.file_role == "test")

            results.append(
                {
                    "id": ds.id,
                    "dataset_code": ds.dataset_code,
                    "source_name": ds.source_name,
                    "source_uri": ds.source_uri,
                    "checksum_sha256": ds.checksum_sha256,
                    "parser_version": ds.parser_version,
                    "preprocessing_version": ds.preprocessing_version,
                    "status": ds.status,
                    "engine_count": len(runs),
                    "train_count": train_count,
                    "test_count": test_count,
                    "has_test_rul": has_rul,
                    "created_at": ds.created_at,
                    "updated_at": ds.updated_at,
                }
            )
        return results

    @staticmethod
    def get_dataset(db: Session, dataset_id: uuid.UUID) -> dict[str, Any] | None:
        ds = db.scalars(
            select(DatasetVersion)
            .where(
                DatasetVersion.id == dataset_id,
            )
            .with_for_update()
        ).first()
        if not ds:
            return None

        runs = ds.engine_runs
        train_count = sum(1 for r in runs if r.file_role == "train")
        test_count = sum(1 for r in runs if r.file_role == "test")
        has_rul = any(r.ground_truth_rul is not None for r in runs if r.file_role == "test")

        file_list = []
        for f in ds.files:
            file_list.append(
                {
                    "id": str(f.id),
                    "file_role": f.file_role,
                    "original_filename": f.original_filename,
                    "row_count": f.row_count,
                    "engine_count": f.engine_count,
                    "status": f.status,
                    "checksum_sha256": f.checksum_sha256,
                    "report": f.report,
                }
            )

        return {
            "id": ds.id,
            "dataset_code": ds.dataset_code,
            "source_name": ds.source_name,
            "source_uri": ds.source_uri,
            "checksum_sha256": ds.checksum_sha256,
            "parser_version": ds.parser_version,
            "preprocessing_version": ds.preprocessing_version,
            "status": ds.status,
            "engine_count": len(runs),
            "train_count": train_count,
            "test_count": test_count,
            "has_test_rul": has_rul,
            "files": file_list,
            "parameters": ds.parameters,
            "created_at": ds.created_at,
            "updated_at": ds.updated_at,
        }

    @staticmethod
    def get_or_create_dataset_version(
        db: Session,
        dataset_code: str = "FD001",
        source_name: str = "User-imported C-MAPSS",
    ) -> DatasetVersion:
        """Create a fresh draft. Callers must explicitly reuse its ID for additional roles."""
        if dataset_code != "FD001":
            raise ValueError("Only FD001 is supported by this preprocessing version")
        ds = DatasetVersion(dataset_code=dataset_code, source_name=source_name, status="imported")
        db.add(ds)
        db.commit()
        db.refresh(ds)
        return ds

    @staticmethod
    def ingest_file_content(
        db: Session,
        dataset_id: uuid.UUID,
        file_role: str,
        filename: str,
        content: str | bytes,
    ) -> dict[str, Any]:
        """Append a validated file role; never replace historical telemetry or labels."""
        ds = db.scalars(
            select(DatasetVersion)
            .where(
                DatasetVersion.id == dataset_id,
            )
            .with_for_update()
        ).first()
        if not ds:
            raise ValueError("Dataset version does not exist")
        if file_role not in ("train", "test", "test_rul"):
            raise ValueError("Invalid file role")
        raw = content.encode("utf-8") if isinstance(content, str) else content
        if len(raw) > get_settings().max_upload_size_mb * 1024 * 1024:
            raise ValueError("Upload exceeds MAX_UPLOAD_SIZE_MB")
        checksum = calculate_sha256(raw)
        existing = db.scalars(
            select(DatasetFile).where(
                DatasetFile.dataset_version_id == dataset_id,
                DatasetFile.file_role == file_role,
                DatasetFile.checksum_sha256 == checksum,
            )
        ).first()
        if existing:
            return {
                "status": "success" if existing.status == "validated" else "failed",
                "report": existing.report,
                "reused": True,
            }
        prior = db.scalars(
            select(DatasetFile).where(
                DatasetFile.dataset_version_id == dataset_id,
                DatasetFile.file_role == file_role,
                DatasetFile.status == "validated",
            )
        ).first()
        if ds.status == "prepared" or prior:
            raise ValueError("Dataset version is immutable. Create a new version to change files.")
        storage = get_settings().raw_storage_path / str(dataset_id)
        storage.mkdir(parents=True, exist_ok=True)
        storage_file = storage / f"{file_role}_{checksum}.txt"
        # Preserve exact source bytes for reproducible checksums, including line endings.
        if not storage_file.exists():
            storage_file.write_bytes(raw)
        parsed, errors, _ = parse_file(storage_file, role=file_role)
        test_runs = db.scalars(
            select(EngineRun)
            .where(
                EngineRun.dataset_version_id == dataset_id,
                EngineRun.file_role == "test",
            )
            .order_by(EngineRun.unit_number)
        ).all()
        if file_role == "test_rul":
            if not test_runs:
                raise ValueError("Import test telemetry before its RUL labels")
            assert isinstance(parsed, np.ndarray)
            report = validate_rul_array(parsed, len(test_runs), errors, checksum)
            if [r.unit_number for r in test_runs] != list(range(1, len(test_runs) + 1)):
                report.errors.append("Test unit IDs must be consecutive from 1 for RUL alignment")
                report.is_valid = False
        else:
            assert isinstance(parsed, pd.DataFrame)
            report = validate_telemetry_dataframe(parsed, file_role, errors, checksum)
        db.add(
            DatasetFile(
                dataset_version_id=dataset_id,
                file_role=file_role,
                original_filename=Path(filename.replace("\\", "/")).name,
                storage_uri=str(storage_file),
                checksum_sha256=checksum,
                row_count=report.accepted_rows,
                engine_count=report.engine_count,
                status="validated" if report.is_valid else "failed",
                report=report.model_dump(),
            )
        )
        if report.is_valid:
            if isinstance(parsed, pd.DataFrame):
                for unit, group in parsed.groupby("unit_number"):
                    run = EngineRun(
                        dataset_version_id=dataset_id,
                        file_role=file_role,
                        unit_number=int(unit),
                        max_cycle=int(group["cycle"].max()),
                    )
                    db.add(run)
                    db.flush()
                    db.add_all(
                        [
                            EngineCycle(
                                engine_run_id=run.id,
                                cycle=int(row["cycle"]),
                                operational_settings=[float(row[c]) for c in SETTINGS_COLUMNS],
                                sensor_values={s: float(row[s]) for s in SENSOR_COLUMNS},
                                quality_flag=True,
                            )
                            for _, row in group.iterrows()
                        ]
                    )
            else:
                for run, rul in zip(test_runs, parsed, strict=True):
                    run.ground_truth_rul = float(rul)
            db.flush()
            files = db.scalars(
                select(DatasetFile)
                .where(
                    DatasetFile.dataset_version_id == dataset_id,
                    DatasetFile.status == "validated",
                )
                .order_by(DatasetFile.file_role)
            ).all()
            ds.checksum_sha256 = calculate_sha256(
                json.dumps(
                    {f.file_role: f.checksum_sha256 for f in files},
                    sort_keys=True,
                )
            )
        db.commit()
        return {"status": "success" if report.is_valid else "failed", "report": report.model_dump()}

    @staticmethod
    def load_samples(db: Session) -> dict[str, Any]:
        """Reuse an identical synthetic fixture version without replacing its runs."""
        sample_dir = get_data_dir() / "samples"
        sources = {
            role: (sample_dir / name).read_bytes()
            for role, name in (
                ("train", "train_FD001.txt"),
                ("test", "test_FD001.txt"),
                ("test_rul", "RUL_FD001.txt"),
            )
        }
        checksums = {role: calculate_sha256(raw) for role, raw in sources.items()}
        versions = db.scalars(
            select(DatasetVersion).where(
                DatasetVersion.source_name == "Synthetic C-MAPSS-shaped FD001 fixtures",
                DatasetVersion.status == "prepared",
            )
        ).all()
        for version in versions:
            if {
                f.file_role: f.checksum_sha256 for f in version.files if f.status == "validated"
            } == checksums:
                return {"dataset_id": str(version.id), "reports": {}, "reused": True}
        ds = DatasetService.get_or_create_dataset_version(
            db,
            source_name="Synthetic C-MAPSS-shaped FD001 fixtures",
        )
        ds.source_uri = "scripts/generate_synthetic_cmapss.py"
        ds.parameters = {"data_kind": "synthetic", "generator_seed": 42}
        db.commit()
        reports = {}
        for role, raw in sources.items():
            reports[role] = DatasetService.ingest_file_content(db, ds.id, role, role + ".txt", raw)
            if reports[role]["status"] != "success":
                raise ValueError(f"Invalid synthetic fixture: {role}")
        DatasetService.prepare_feature_set(db, ds.id)
        return {"dataset_id": str(ds.id), "reports": reports}

    @staticmethod
    def prepare_feature_set(db: Session, dataset_id: uuid.UUID, rul_cap: int = 125) -> FeatureSet:
        """Seal a source version and persist a reproducible full-training feature snapshot.

        Experiments create separate snapshots fitted only on their training partition.
        """
        ds = db.scalars(
            select(DatasetVersion)
            .where(
                DatasetVersion.id == dataset_id,
            )
            .with_for_update()
        ).first()
        if not ds:
            raise ValueError("Dataset not found")
        existing = db.scalars(
            select(FeatureSet).where(
                FeatureSet.dataset_version_id == dataset_id,
                FeatureSet.name == "source-snapshot",
            )
        ).first()
        if existing:
            if existing.parameters["rul_cap"] != rul_cap:
                raise ValueError("Prepared source snapshot already uses a different RUL cap")
            return existing
        train_df = training_dataframe(db, dataset_id)
        preprocessor = LeakFreePreprocessor(rul_cap=rul_cap)
        features, targets, manifest = preprocessor.fit_transform(train_df)
        fs = persist_feature_snapshot(
            db, dataset_id, "source-snapshot", features, targets, manifest.to_dict()
        )
        ds.status = "prepared"
        db.commit()
        return fs


def training_dataframe(db: Session, dataset_id: uuid.UUID) -> pd.DataFrame:
    runs = db.scalars(
        select(EngineRun)
        .where(
            EngineRun.dataset_version_id == dataset_id,
            EngineRun.file_role == "train",
        )
        .order_by(EngineRun.unit_number)
    ).all()
    rows = []
    for run in runs:
        for cycle in sorted(run.cycles, key=lambda c: c.cycle):
            rows.append(
                {
                    "unit_number": run.unit_number,
                    "cycle": cycle.cycle,
                    **dict(zip(SETTINGS_COLUMNS, cycle.operational_settings, strict=True)),
                    **cycle.sensor_values,
                }
            )
    if not rows:
        raise ValueError("No training engine runs found in dataset")
    return pd.DataFrame(rows)


def persist_feature_snapshot(
    db: Session,
    dataset_id: uuid.UUID,
    name: str,
    features: pd.DataFrame,
    targets: pd.Series,
    parameters: dict[str, Any],
) -> FeatureSet:
    fs = FeatureSet(dataset_version_id=dataset_id, name=name, parameters=parameters)
    db.add(fs)
    db.flush()
    directory = get_settings().processed_storage_path / str(fs.id)
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = features.copy()
    snapshot["rul_target"] = targets
    feature_file = directory / "features.csv"
    snapshot.to_csv(feature_file, index=False)
    manifest = {**parameters, "snapshot_sha256": calculate_sha256(feature_file.read_bytes())}
    manifest_file = directory / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    fs.parameters = manifest
    fs.feature_manifest_uri = str(manifest_file)
    return fs
