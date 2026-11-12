"""Unit tests for C-MAPSS parser, validator, and leak-free feature pipelines."""

import numpy as np
import pandas as pd
import pytest

from app.pipelines.constants import ALL_COLUMNS
from app.pipelines.features import (
    LeakFreePreprocessor,
    calculate_capped_rul,
)
from app.pipelines.parser import parse_rul_content, parse_telemetry_content
from app.pipelines.validator import validate_rul_array, validate_telemetry_dataframe


def test_parser_parses_valid_whitespace_telemetry() -> None:
    # 26 columns whitespace-delimited
    sample_row = "1 1 0.0023 0.0003 100.0 " + " ".join([str(500.0 + i) for i in range(21)])
    df, errors = parse_telemetry_content(sample_row)

    assert len(errors) == 0
    assert len(df) == 1
    assert df["unit_number"].iloc[0] == 1
    assert df["cycle"].iloc[0] == 1
    assert df["operational_setting_1"].iloc[0] == pytest.approx(0.0023)
    assert df["sensor_1"].iloc[0] == pytest.approx(500.0)


def test_parser_captures_malformed_columns() -> None:
    bad_row = "1 1 0.0023 0.0003"  # Only 4 columns instead of 26
    df, errors = parse_telemetry_content(bad_row)

    assert len(errors) == 1
    assert "expected 26 columns" in errors[0]
    assert len(df) == 0


def test_parser_parses_rul_file() -> None:
    rul_text = "112\n98\n42\n"
    arr, errors = parse_rul_content(rul_text)

    assert len(errors) == 0
    assert len(arr) == 3
    assert np.array_equal(arr, [112.0, 98.0, 42.0])


def test_validator_detects_non_monotonic_cycles() -> None:
    # Engine unit 1 with cycle sequence [1, 2, 4, 3]
    rows = []
    cycles = [1, 2, 4, 3]
    for c in cycles:
        row = [1, c, 0.0, 0.0, 100.0] + [500.0] * 21
        rows.append(row)
    df = pd.DataFrame(rows, columns=ALL_COLUMNS)

    report = validate_telemetry_dataframe(df, role="train", parser_errors=[], checksum="dummy")
    assert not report.is_valid
    assert any("non-monotonic" in err for err in report.errors)


def test_validator_passes_valid_telemetry() -> None:
    rows = []
    for c in range(1, 10):
        row = [1, c, 0.0, 0.0, 100.0] + [500.0 + c] * 21
        rows.append(row)
    df = pd.DataFrame(rows, columns=ALL_COLUMNS)

    report = validate_telemetry_dataframe(
        df, role="train", parser_errors=[], checksum="test_checksum"
    )
    assert report.is_valid
    assert report.accepted_rows == 9
    assert report.engine_count == 1
    assert report.unit_max_cycles[1] == 9


def test_validator_validates_rul_length_and_non_negative() -> None:
    ruls = np.array([50, -5, 20])
    report = validate_rul_array(ruls, expected_units_count=3, parser_errors=[], checksum="chk")
    assert not report.is_valid
    assert any("non-negative" in err for err in report.errors)

    mismatch_report = validate_rul_array(
        np.array([50, 20]), expected_units_count=3, parser_errors=[], checksum="chk"
    )
    assert not mismatch_report.is_valid
    assert any("mismatch" in err for err in mismatch_report.errors)


def test_capped_rul_target_calculation() -> None:
    # Unit 1 with 200 cycles
    df = pd.DataFrame(
        {
            "unit_number": [1] * 200,
            "cycle": list(range(1, 201)),
        }
    )
    target = calculate_capped_rul(df, rul_cap=125)

    # At cycle 1, raw RUL = 199, capped = 125
    assert target.iloc[0] == 125.0
    # At cycle 75, raw RUL = 125, capped = 125
    assert target.iloc[74] == 125.0
    # At cycle 100, raw RUL = 100, capped = 100
    assert target.iloc[99] == 100.0
    # At final cycle 200, raw RUL = 0, capped = 0
    assert target.iloc[199] == 0.0


def test_leak_free_preprocessor_preserves_engine_isolation() -> None:
    # Create two engines
    rows = []
    for u in [1, 2]:
        for c in range(1, 20):
            # Give sensor 2 a variance, and sensor 1 constant value
            s1 = 518.67
            s2 = 640.0 + c * 0.5 if u == 1 else 642.0 + c * 0.3
            rows.append([u, c, 0.0, 0.0, 100.0, s1, s2] + [500.0] * 19)

    cols = [
        "unit_number",
        "cycle",
        "operational_setting_1",
        "operational_setting_2",
        "operational_setting_3",
        "sensor_1",
        "sensor_2",
    ] + [f"sensor_{i}" for i in range(3, 22)]
    df = pd.DataFrame(rows, columns=cols)

    preprocessor = LeakFreePreprocessor(rul_cap=125)
    X_train, y_train, manifest = preprocessor.fit_transform(df)

    # Check that sensor 1 was identified as invariant and dropped
    assert "sensor_1" in manifest.dropped_sensors
    assert "sensor_2" in manifest.selected_sensors
    assert len(X_train) == len(df)
    assert len(y_train) == len(df)

    # Transform a simulated test engine using the pre-fitted scaler
    test_df = df[df["unit_number"] == 2].copy()
    X_test = preprocessor.transform(test_df)
    assert len(X_test) == len(test_df)
    assert list(X_test.columns) == list(X_train.columns)
