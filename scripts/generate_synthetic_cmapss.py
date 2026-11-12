"""Synthetic NASA C-MAPSS FD001 data generator.

Generates reproducible, physically grounded synthetic C-MAPSS datasets for:
1. Committed test fixtures (train, test, and test_rul)
2. Negative test fixtures for parser and validator verification
"""

import argparse
from pathlib import Path
import numpy as np


def generate_engine_sequence(
    unit_id: int,
    total_cycles: int,
    is_truncated: bool = False,
    remaining_cycles: int = 0,
    seed: int | None = None,
) -> tuple[np.ndarray, int]:
    """Generates synthetic telemetry rows for a single turbofan engine."""
    rng = np.random.default_rng(seed)
    
    # If truncated, the sequence ends early with `remaining_cycles` left before failure
    effective_cycles = total_cycles - remaining_cycles if is_truncated else total_cycles
    
    # Health index degrades exponentially towards zero as cycle approaches total_cycles
    t = np.arange(1, effective_cycles + 1)
    progress = t / float(total_cycles)
    
    # Exponential wear curve: initial slow degradation, accelerating near end-of-life
    wear = np.power(progress, 2.5)
    
    # Base operational settings (FD001 Sea Level: settings ~0, 0, 100)
    op1 = rng.normal(0.0, 0.0015, size=effective_cycles)
    op2 = rng.normal(0.0, 0.0003, size=effective_cycles)
    op3 = np.full(effective_cycles, 100.0)
    
    # Invariant sensors (7 sensors in FD001)
    s1 = np.full(effective_cycles, 518.67)
    s5 = np.full(effective_cycles, 14.62)
    s6 = np.full(effective_cycles, 21.61)
    s10 = np.full(effective_cycles, 1.30)
    s16 = np.full(effective_cycles, 0.03)
    s18 = np.full(effective_cycles, 2388.0)
    s19 = np.full(effective_cycles, 100.0)
    
    # Informative Degrading Sensors (14 sensors with physical trends and noise)
    s2 = 642.0 + 2.5 * wear + rng.normal(0, 0.15, size=effective_cycles)
    s3 = 1585.0 + 25.0 * wear + rng.normal(0, 1.2, size=effective_cycles)
    s4 = 1400.0 + 30.0 * wear + rng.normal(0, 1.5, size=effective_cycles)
    s7 = 554.0 - 3.5 * wear + rng.normal(0, 0.18, size=effective_cycles)
    s8 = 2388.05 + 0.15 * wear + rng.normal(0, 0.03, size=effective_cycles)
    s9 = 9050.0 + 25.0 * wear + rng.normal(0, 2.0, size=effective_cycles)
    s11 = 47.25 + 0.9 * wear + rng.normal(0, 0.06, size=effective_cycles)
    s12 = 521.8 - 3.0 * wear + rng.normal(0, 0.25, size=effective_cycles)
    s13 = 2388.07 + 0.12 * wear + rng.normal(0, 0.03, size=effective_cycles)
    s14 = 8130.0 + 15.0 * wear + rng.normal(0, 1.5, size=effective_cycles)
    s15 = 8.42 + 0.12 * wear + rng.normal(0, 0.015, size=effective_cycles)
    s17 = 391.0 + 6.0 * wear + rng.normal(0, 0.5, size=effective_cycles)
    s20 = 38.9 - 0.7 * wear + rng.normal(0, 0.05, size=effective_cycles)
    s21 = 23.35 - 0.45 * wear + rng.normal(0, 0.04, size=effective_cycles)
    
    # Assemble canonical 26 columns
    unit_col = np.full(effective_cycles, unit_id, dtype=int)
    cycle_col = t
    
    rows = np.column_stack([
        unit_col, cycle_col, op1, op2, op3,
        s1, s2, s3, s4, s5, s6, s7, s8, s9, s10,
        s11, s12, s13, s14, s15, s16, s17, s18, s19, s20, s21
    ])
    
    return rows, (remaining_cycles if is_truncated else 0)


def generate_dataset(
    output_dir: Path,
    num_train_units: int = 15,
    num_test_units: int = 10,
    seed: int = 42,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    
    # 1. Generate Training Set (run to failure)
    train_rows_list = []
    for u in range(1, num_train_units + 1):
        total_life = int(rng.integers(140, 260))
        unit_seed = int(rng.integers(0, 100000))
        rows, _ = generate_engine_sequence(
            unit_id=u,
            total_cycles=total_life,
            is_truncated=False,
            seed=unit_seed,
        )
        train_rows_list.append(rows)
    
    train_data = np.vstack(train_rows_list)
    train_path = output_dir / "train_FD001.txt"
    np.savetxt(
        train_path,
        train_data,
        fmt=["%d", "%d"] + ["%.4f", "%.4f", "%.1f"] + ["%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.4f", "%.2f", "%d", "%d", "%.2f", "%.2f", "%.4f"],
        delimiter=" ",
    )
    print(f"Generated train set: {train_path} ({len(train_data)} rows across {num_train_units} units)")
    
    # 2. Generate Test Set and Test RUL ground truth
    test_rows_list = []
    test_ruls = []
    for u in range(1, num_test_units + 1):
        total_life = int(rng.integers(150, 250))
        # Random remaining cycles at truncation
        rul = int(rng.integers(8, 115))
        unit_seed = int(rng.integers(0, 100000))
        rows, true_rul = generate_engine_sequence(
            unit_id=u,
            total_cycles=total_life,
            is_truncated=True,
            remaining_cycles=rul,
            seed=unit_seed,
        )
        test_rows_list.append(rows)
        test_ruls.append(true_rul)
    
    test_data = np.vstack(test_rows_list)
    test_path = output_dir / "test_FD001.txt"
    np.savetxt(
        test_path,
        test_data,
        fmt=["%d", "%d"] + ["%.4f", "%.4f", "%.1f"] + ["%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.2f", "%.4f", "%.2f", "%d", "%d", "%.2f", "%.2f", "%.4f"],
        delimiter=" ",
    )
    print(f"Generated test set: {test_path} ({len(test_data)} rows across {num_test_units} units)")
    
    rul_path = output_dir / "RUL_FD001.txt"
    np.savetxt(rul_path, np.array(test_ruls, dtype=int), fmt="%d")
    print(f"Generated test RUL ground truth: {rul_path} ({len(test_ruls)} units)")
    
    # 3. Generate Malformed Negative Test Fixtures
    fixtures_dir = output_dir / "invalid"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    # A) Missing columns (only 20 columns instead of 26)
    bad_cols_path = fixtures_dir / "invalid_columns_FD001.txt"
    np.savetxt(bad_cols_path, train_data[:20, :20], fmt="%.2f", delimiter=" ")
    
    # B) Non-monotonic cycles (e.g. cycle 5 followed by cycle 3)
    bad_order_data = train_data[:10].copy()
    bad_order_data[4, 1] = 2  # inject non-increasing cycle
    bad_order_path = fixtures_dir / "invalid_cycle_order_FD001.txt"
    np.savetxt(bad_order_path, bad_order_data, fmt="%.2f", delimiter=" ")
    
    # C) Non-numeric content
    bad_content_path = fixtures_dir / "invalid_non_numeric_FD001.txt"
    with open(bad_content_path, "w", encoding="utf-8") as f:
        f.write("1 1 0.002 0.000 100.0 518.67 CORRUPT_VALUE 1585.0\n")
        
    print(f"Generated negative validation fixtures in {fixtures_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic C-MAPSS FD001 fixtures")
    parser.add_argument("--output-dir", type=Path, default=Path("data/samples"))
    parser.add_argument("--train-units", type=int, default=15)
    parser.add_argument("--test-units", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    generate_dataset(
        output_dir=args.output_dir,
        num_train_units=args.train_units,
        num_test_units=args.test_units,
        seed=args.seed,
    )
