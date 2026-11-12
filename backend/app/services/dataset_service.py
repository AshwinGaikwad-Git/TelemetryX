"""Service for managing C-MAPSS dataset versions, raw file ingestion, and validation."""

import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

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
        ds = db.get(DatasetVersion, dataset_id)
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
        source_name: str = "NASA C-MAPSS Simulation",
    ) -> DatasetVersion:
        stmt = (
            select(DatasetVersion)
            .where(DatasetVersion.dataset_code == dataset_code)
            .order_by(DatasetVersion.created_at.desc())
        )
        existing = db.scalars(stmt).first()
        if existing and existing.status in ("imported", "prepared"):
            return existing

        ds = DatasetVersion(
            dataset_code=dataset_code,
            source_name=source_name,
            source_uri="https://data.nasa.gov/Aerospace/CMAPSS-Data/ff5v-kuh6",
            status="imported",
        )
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
        """Ingests, parses, validates, and persists a C-MAPSS file."""
        ds = db.get(DatasetVersion, dataset_id)
        if not ds:
            raise ValueError(f"DatasetVersion {dataset_id} does not exist")

        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        checksum = calculate_sha256(content)

        # 1. Save raw file copy locally
        raw_storage = get_data_dir() / "raw"
        raw_storage.mkdir(parents=True, exist_ok=True)
        storage_file = raw_storage / f"{dataset_id}_{file_role}_{filename}"
        storage_file.write_text(text, encoding="utf-8")

        # 2. Parse & Validate
        if file_role in ("train", "test"):
            df, parser_errors, _ = parse_file(storage_file, role=file_role)
            if not isinstance(df, pd.DataFrame):
                raise ValueError("Expected DataFrame for telemetry file")
            report = validate_telemetry_dataframe(
                df, role=file_role, parser_errors=parser_errors, checksum=checksum
            )

            if not report.is_valid:
                # Save failed file audit
                ds_file = DatasetFile(
                    dataset_version_id=dataset_id,
                    file_role=file_role,
                    original_filename=filename,
                    storage_uri=str(storage_file),
                    checksum_sha256=checksum,
                    status="failed",
                    report=report.model_dump(),
                )
                db.add(ds_file)
                db.commit()
                return {"status": "failed", "report": report.model_dump()}

            # 3. Persist engine runs and cycles
            # Delete any existing runs for this role and dataset version to maintain idempotency
            existing_runs = db.scalars(
                select(EngineRun).where(
                    EngineRun.dataset_version_id == dataset_id,
                    EngineRun.file_role == file_role,
                )
            ).all()
            for r in existing_runs:
                db.delete(r)
            db.flush()

            for unit_number, group in df.groupby("unit_number"):
                max_cycle = int(group["cycle"].max())
                run = EngineRun(
                    dataset_version_id=dataset_id,
                    file_role=file_role,
                    unit_number=int(unit_number),
                    max_cycle=max_cycle,
                )
                db.add(run)
                db.flush()

                # Add telemetry cycles
                cycles_to_add = []
                for _, row in group.iterrows():
                    op_settings = [float(row[c]) for c in SETTINGS_COLUMNS]
                    sensor_vals = {s: float(row[s]) for s in SENSOR_COLUMNS}
                    cycles_to_add.append(
                        EngineCycle(
                            engine_run_id=run.id,
                            cycle=int(row["cycle"]),
                            operational_settings=op_settings,
                            sensor_values=sensor_vals,
                            quality_flag=True,
                        )
                    )
                db.add_all(cycles_to_add)

            # Delete prior existing file with same checksum if present
            existing_file = db.scalars(
                select(DatasetFile).where(
                    DatasetFile.dataset_version_id == dataset_id,
                    DatasetFile.file_role == file_role,
                    DatasetFile.checksum_sha256 == checksum,
                )
            ).first()
            if existing_file:
                db.delete(existing_file)
                db.flush()

            ds_file = DatasetFile(
                dataset_version_id=dataset_id,
                file_role=file_role,
                original_filename=filename,
                storage_uri=str(storage_file),
                checksum_sha256=checksum,
                row_count=report.accepted_rows,
                engine_count=report.engine_count,
                status="validated",
                report=report.model_dump(),
            )
            db.add(ds_file)
            db.commit()

        elif file_role == "test_rul":
            rul_arr, parser_errors, _ = parse_file(storage_file, role="test_rul")
            if not isinstance(rul_arr, np.ndarray):
                raise ValueError("Expected numpy array for RUL file")

            # Check test units count
            test_runs = db.scalars(
                select(EngineRun)
                .where(
                    EngineRun.dataset_version_id == dataset_id,
                    EngineRun.file_role == "test",
                )
                .order_by(EngineRun.unit_number.asc())
            ).all()
            expected_count = len(test_runs) if test_runs else None

            report = validate_rul_array(
                rul_arr,
                expected_units_count=expected_count,
                parser_errors=parser_errors,
                checksum=checksum,
            )

            if not report.is_valid:
                ds_file = DatasetFile(
                    dataset_version_id=dataset_id,
                    file_role=file_role,
                    original_filename=filename,
                    storage_uri=str(storage_file),
                    checksum_sha256=checksum,
                    status="failed",
                    report=report.model_dump(),
                )
                db.add(ds_file)
                db.commit()
                return {"status": "failed", "report": report.model_dump()}

            # Assign ground truth RUL to test engines in unit order
            for idx, r in enumerate(test_runs):
                if idx < len(rul_arr):
                    r.ground_truth_rul = float(rul_arr[idx])

            # Delete prior existing file with same checksum if present
            existing_file = db.scalars(
                select(DatasetFile).where(
                    DatasetFile.dataset_version_id == dataset_id,
                    DatasetFile.file_role == file_role,
                    DatasetFile.checksum_sha256 == checksum,
                )
            ).first()
            if existing_file:
                db.delete(existing_file)
                db.flush()

            ds_file = DatasetFile(
                dataset_version_id=dataset_id,
                file_role=file_role,
                original_filename=filename,
                storage_uri=str(storage_file),
                checksum_sha256=checksum,
                row_count=len(rul_arr),
                engine_count=len(rul_arr),
                status="validated",
                report=report.model_dump(),
            )
            db.add(ds_file)
            db.commit()

        return {"status": "success", "report": report.model_dump()}

    @staticmethod
    def load_samples(db: Session) -> dict[str, Any]:
        """Loads and prepares the committed synthetic C-MAPSS FD001 sample fixtures."""
        ds = DatasetService.get_or_create_dataset_version(
            db, dataset_code="FD001", source_name="NASA C-MAPSS Simulation Sample"
        )
        sample_dir = get_data_dir() / "samples"

        train_path = sample_dir / "train_FD001.txt"
        test_path = sample_dir / "test_FD001.txt"
        rul_path = sample_dir / "RUL_FD001.txt"

        reports = {}
        if train_path.exists():
            rep = DatasetService.ingest_file_content(
                db, ds.id, "train", "train_FD001.txt", train_path.read_text(encoding="utf-8")
            )
            reports["train"] = rep

        if test_path.exists():
            rep = DatasetService.ingest_file_content(
                db, ds.id, "test", "test_FD001.txt", test_path.read_text(encoding="utf-8")
            )
            reports["test"] = rep

        if rul_path.exists():
            rep = DatasetService.ingest_file_content(
                db, ds.id, "test_rul", "RUL_FD001.txt", rul_path.read_text(encoding="utf-8")
            )
            reports["test_rul"] = rep

        # Build feature set
        DatasetService.prepare_feature_set(db, ds.id)
        return {"dataset_id": ds.id, "reports": reports}

    @staticmethod
    def prepare_feature_set(db: Session, dataset_id: uuid.UUID, rul_cap: int = 125) -> FeatureSet:
        """Constructs an immutable feature set from training telemetry with zero leakage."""
        ds = db.get(DatasetVersion, dataset_id)
        if not ds:
            raise ValueError("Dataset not found")

        # Load training cycles
        runs = db.scalars(
            select(EngineRun).where(
                EngineRun.dataset_version_id == dataset_id,
                EngineRun.file_role == "train",
            )
        ).all()
        if not runs:
            raise ValueError("No training engine runs found in dataset")

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

        train_df = pd.DataFrame(rows)

        preprocessor = LeakFreePreprocessor(rul_cap=rul_cap)
        _, _, manifest = preprocessor.fit_transform(train_df)

        # Save feature set record
        feat_set = FeatureSet(
            dataset_version_id=dataset_id,
            name=f"features-{ds.dataset_code}-v1",
            parameters=manifest.to_dict(),
        )
        db.add(feat_set)
        ds.status = "prepared"
        db.commit()
        db.refresh(feat_set)
        return feat_set
