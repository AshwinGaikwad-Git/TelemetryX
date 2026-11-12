"""Validator for C-MAPSS telemetry datasets and ground-truth RUL files."""

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from app.pipelines.constants import ALL_COLUMNS


class ValidationReport(BaseModel):
    is_valid: bool
    role: str
    accepted_rows: int
    rejected_rows: int
    engine_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checksum_sha256: str
    unit_max_cycles: dict[int, int] = Field(default_factory=dict)


def validate_telemetry_dataframe(
    df: pd.DataFrame,
    role: str,
    parser_errors: list[str],
    checksum: str,
) -> ValidationReport:
    """Performs structural and semantic validation on a parsed C-MAPSS telemetry DataFrame."""
    errors = list(parser_errors)
    warnings: list[str] = []

    if df.empty:
        errors.append("Dataset contains no valid telemetry records")
        return ValidationReport(
            is_valid=False,
            role=role,
            accepted_rows=0,
            rejected_rows=len(errors),
            engine_count=0,
            errors=errors,
            warnings=warnings,
            checksum_sha256=checksum,
            unit_max_cycles={},
        )

    # 1. Check required columns
    missing_cols = [col for col in ALL_COLUMNS if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")

    # 2. Check for NaN or Infinite values
    numeric_df = df[ALL_COLUMNS]
    if numeric_df.isna().any().any():
        nan_cols = numeric_df.columns[numeric_df.isna().any()].tolist()
        errors.append(f"NaN values detected in columns: {nan_cols}")

    if np.isinf(numeric_df.to_numpy()).any():
        errors.append("Infinite values detected in numerical telemetry columns")

    # 3. Unit number and cycle positive integer constraints
    if (df["unit_number"] <= 0).any():
        errors.append("Engine unit numbers must be strictly positive integers (> 0)")

    if (df["cycle"] <= 0).any():
        errors.append("Operational cycles must be strictly positive integers (> 0)")

    # 4. Strict monotonic increase of cycles per engine unit
    unit_max_cycles: dict[int, int] = {}
    grouped = df.groupby("unit_number")
    for unit, group in grouped:
        cycles = group["cycle"].to_numpy()
        # Check uniqueness
        if len(cycles) != len(np.unique(cycles)):
            errors.append(f"Unit {unit} contains duplicate cycle numbers")

        # Check strictly monotonic increasing
        diffs = np.diff(cycles)
        if not np.all(diffs > 0):
            errors.append(f"Unit {unit} contains non-monotonic cycle sequence")
        elif not np.all(diffs == 1):
            warnings.append(f"Unit {unit} has gaps in cycle increments (expected increment of 1)")

        unit_max_cycles[int(unit)] = int(cycles.max())

    engine_count = len(grouped)
    accepted_rows = len(df)
    rejected_rows = len(parser_errors)
    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        role=role,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        engine_count=engine_count,
        errors=errors,
        warnings=warnings,
        checksum_sha256=checksum,
        unit_max_cycles=unit_max_cycles,
    )


def validate_rul_array(
    rul_array: np.ndarray,
    expected_units_count: int | None,
    parser_errors: list[str],
    checksum: str,
) -> ValidationReport:
    """Validates an RUL ground truth array against test engine requirements."""
    errors = list(parser_errors)
    warnings: list[str] = []

    if len(rul_array) == 0:
        errors.append("RUL ground truth file is empty")
    elif not np.isfinite(rul_array).all():
        errors.append("RUL values must be finite")
    elif (rul_array < 0).any():
        errors.append("RUL values must be non-negative integers/floats (>= 0)")

    if expected_units_count is not None and len(rul_array) != expected_units_count:
        errors.append(
            f"RUL count mismatch: ground truth has {len(rul_array)} rows, "
            f"but test dataset has {expected_units_count} engines"
        )

    is_valid = len(errors) == 0
    return ValidationReport(
        is_valid=is_valid,
        role="test_rul",
        accepted_rows=len(rul_array),
        rejected_rows=len(parser_errors),
        engine_count=len(rul_array),
        errors=errors,
        warnings=warnings,
        checksum_sha256=checksum,
        unit_max_cycles={},
    )
