"""Parser for whitespace-delimited NASA C-MAPSS dataset files."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from app.pipelines.constants import ALL_COLUMNS


def calculate_sha256(content: str | bytes) -> str:
    """Calculate the SHA-256 hash of text or byte content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def parse_telemetry_content(raw_text: str) -> tuple[pd.DataFrame, list[str]]:
    """Parses raw text of a C-MAPSS train or test file into a DataFrame.

    Returns:
        (DataFrame with canonical columns, list of error messages for rejected rows)
    """
    lines = raw_text.strip().splitlines()
    rows = []
    errors = []

    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 26:
            errors.append(f"Line {line_idx}: expected 26 columns, found {len(parts)}")
            continue
        # C-MAPSS files sometimes have extra trailing empty tokens or trailing spaces
        if len(parts) > 26:
            # If extra tokens are present, verify if they can be safely ignored
            parts = parts[:26]

        try:
            unit = int(parts[0])
            cycle = int(parts[1])
            floats = [float(p) for p in parts[2:26]]
            rows.append([unit, cycle] + floats)
        except ValueError as ex:
            errors.append(f"Line {line_idx}: non-numeric value ({ex})")

    if not rows:
        return pd.DataFrame(columns=ALL_COLUMNS), errors

    df = pd.DataFrame(rows, columns=ALL_COLUMNS)
    df["unit_number"] = df["unit_number"].astype(int)
    df["cycle"] = df["cycle"].astype(int)
    for col in ALL_COLUMNS[2:]:
        df[col] = df[col].astype(float)

    return df, errors


def parse_rul_content(raw_text: str) -> tuple[np.ndarray, list[str]]:
    """Parses raw text of an RUL ground truth file into a 1D numpy array."""
    lines = raw_text.strip().splitlines()
    ruls = []
    errors = []

    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if not parts:
            continue
        try:
            val = float(parts[0])
            ruls.append(val)
        except ValueError as ex:
            errors.append(f"Line {line_idx}: non-numeric RUL value ({ex})")

    return np.array(ruls, dtype=float), errors


def parse_file(
    file_path: Path | str, role: str
) -> tuple[pd.DataFrame | np.ndarray, list[str], str]:
    """Reads and parses a file given its path and role ('train', 'test', 'test_rul').

    Returns:
        (Parsed data, errors, sha256_checksum)
    """
    path = Path(file_path)
    content_bytes = path.read_bytes()
    checksum = calculate_sha256(content_bytes)
    text = content_bytes.decode("utf-8", errors="replace")

    if role in ("train", "test"):
        data, errors = parse_telemetry_content(text)
    elif role == "test_rul":
        data, errors = parse_rul_content(text)
    else:
        raise ValueError(f"Unknown file role: {role}")

    return data, errors, checksum
