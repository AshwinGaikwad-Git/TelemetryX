"""Feature engineering, RUL target derivation, and leak-free preprocessing."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from app.pipelines.constants import (
    DEFAULT_ROLLING_WINDOWS,
    DEFAULT_RUL_CAP,
    FD001_INFORMATIVE_SENSORS,
    FD001_INVARIANT_SENSORS,
    SETTINGS_COLUMNS,
)


@dataclass
class FeatureManifest:
    feature_names: list[str]
    selected_sensors: list[str]
    dropped_sensors: list[str]
    rolling_windows: list[int]
    rul_cap: int
    scaler_mean: list[float]
    scaler_scale: list[float]
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "selected_sensors": self.selected_sensors,
            "dropped_sensors": self.dropped_sensors,
            "rolling_windows": self.rolling_windows,
            "rul_cap": self.rul_cap,
            "scaler_mean": self.scaler_mean,
            "scaler_scale": self.scaler_scale,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureManifest":
        return cls(
            feature_names=data["feature_names"],
            selected_sensors=data["selected_sensors"],
            dropped_sensors=data["dropped_sensors"],
            rolling_windows=data["rolling_windows"],
            rul_cap=data["rul_cap"],
            scaler_mean=data["scaler_mean"],
            scaler_scale=data["scaler_scale"],
            extra=data.get("extra", {}),
        )


def identify_informative_sensors(
    train_df: pd.DataFrame, variance_threshold: float = 1e-4
) -> tuple[list[str], list[str]]:
    """Identifies informative sensors vs constant sensors strictly from the training split."""
    all_sensor_cols = [f"sensor_{i}" for i in range(1, 22) if f"sensor_{i}" in train_df.columns]
    selected = []
    dropped = []

    for col in all_sensor_cols:
        col_std = float(train_df[col].std())
        if col_std <= variance_threshold or np.isnan(col_std):
            dropped.append(col)
        else:
            selected.append(col)

    # Fallback to standard FD001 informative list if dataset is small
    if not selected:
        selected = [s for s in FD001_INFORMATIVE_SENSORS if s in train_df.columns]
        dropped = [s for s in FD001_INVARIANT_SENSORS if s in train_df.columns]

    return selected, dropped


def calculate_capped_rul(df: pd.DataFrame, rul_cap: int = DEFAULT_RUL_CAP) -> pd.Series:
    """Calculates piece-wise linear capped Remaining Useful Life (RUL) for training engine runs."""
    # Find max cycle per unit
    max_cycles = df.groupby("unit_number")["cycle"].transform("max")
    raw_rul = max_cycles - df["cycle"]
    capped_rul = raw_rul.clip(upper=rul_cap).astype(float)
    return capped_rul


def engineer_features(
    df: pd.DataFrame,
    selected_sensors: list[str],
    windows: list[int] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    """Derives domain-aware features per engine unit:
    - Raw informative sensors and operational settings
    - Normalized cycle
    - Rolling window mean, std, and lag deltas
    - Rolling linear slope approximation
    """
    feature_dfs = []

    # Process per engine unit to prevent any sequence mixing across units
    for _, unit_df in df.groupby("unit_number", sort=False):
        u_df = unit_df.sort_values("cycle").copy()

        cols_data: dict[str, Any] = {
            "unit_number": u_df["unit_number"],
            "cycle": u_df["cycle"],
            "cycle_norm": u_df["cycle"] / 100.0,
        }

        # Base operational settings
        for setting in SETTINGS_COLUMNS:
            if setting in u_df.columns:
                cols_data[setting] = u_df[setting]

        # Base selected sensors
        for sensor in selected_sensors:
            cols_data[sensor] = u_df[sensor]

        # Rolling aggregates
        for w in windows:
            for s in selected_sensors:
                roll = u_df[s].rolling(window=w, min_periods=1)
                cols_data[f"{s}_roll_mean_{w}"] = roll.mean()
                cols_data[f"{s}_roll_std_{w}"] = roll.std().fillna(0.0)
                lag = (u_df[s] - u_df[s].shift(w)).fillna(0.0)
                cols_data[f"{s}_lag_delta_{w}"] = lag
                cols_data[f"{s}_slope_{w}"] = lag / float(w)

        feature_dfs.append(pd.DataFrame(cols_data, index=u_df.index))

    result_df = pd.concat(feature_dfs, axis=0).sort_index()
    return result_df


class LeakFreePreprocessor:
    """Prepares training, validation, and test datasets with strict leakage controls."""

    def __init__(
        self,
        rul_cap: int = DEFAULT_RUL_CAP,
        rolling_windows: list[int] | None = None,
    ) -> None:
        self.rul_cap = rul_cap
        self.rolling_windows = rolling_windows or DEFAULT_ROLLING_WINDOWS
        self.scaler = StandardScaler()
        self.manifest: FeatureManifest | None = None

    def fit_transform(
        self, train_df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Series, FeatureManifest]:
        """Fits feature selection and scaler on training engines, and returns X, y, manifest."""
        selected_sensors, dropped_sensors = identify_informative_sensors(train_df)

        # 1. Engineer features
        engineered_train = engineer_features(
            train_df, selected_sensors=selected_sensors, windows=self.rolling_windows
        )

        # Separate feature columns from unit and cycle
        feature_cols = [c for c in engineered_train.columns if c not in ("unit_number", "cycle")]

        # 2. Fit and transform scaler on training features ONLY
        X_train_raw = engineered_train[feature_cols].to_numpy()
        self.scaler.fit(X_train_raw)

        X_scaled = pd.DataFrame(
            self.scaler.transform(X_train_raw),
            columns=feature_cols,
            index=engineered_train.index,
        )
        X_scaled.insert(0, "cycle", engineered_train["cycle"])
        X_scaled.insert(0, "unit_number", engineered_train["unit_number"])

        # 3. Compute capped RUL target
        y_train = calculate_capped_rul(train_df, rul_cap=self.rul_cap)

        # 4. Construct manifest
        self.manifest = FeatureManifest(
            feature_names=feature_cols,
            selected_sensors=selected_sensors,
            dropped_sensors=dropped_sensors,
            rolling_windows=self.rolling_windows,
            rul_cap=self.rul_cap,
            scaler_mean=self.scaler.mean_.tolist(),
            scaler_scale=self.scaler.scale_.tolist(),
        )

        return X_scaled, y_train, self.manifest

    def transform(
        self, test_df: pd.DataFrame, manifest: FeatureManifest | None = None
    ) -> pd.DataFrame:
        """Transforms validation or test engine runs using pre-fitted parameters without leakage."""
        active_manifest = manifest or self.manifest
        if active_manifest is None:
            raise ValueError(
                "Preprocessor must be fit before transforming, or manifest must be supplied"
            )

        engineered_test = engineer_features(
            test_df,
            selected_sensors=active_manifest.selected_sensors,
            windows=active_manifest.rolling_windows,
        )

        feature_cols = active_manifest.feature_names
        X_raw = engineered_test[feature_cols].to_numpy()

        scaler = StandardScaler()
        scaler.mean_ = np.array(active_manifest.scaler_mean, dtype=float)
        scaler.scale_ = np.array(active_manifest.scaler_scale, dtype=float)
        scaler.var_ = scaler.scale_**2
        scaler.n_features_in_ = len(feature_cols)

        X_scaled = pd.DataFrame(
            scaler.transform(X_raw),
            columns=feature_cols,
            index=engineered_test.index,
        )
        X_scaled.insert(0, "cycle", engineered_test["cycle"])
        X_scaled.insert(0, "unit_number", engineered_test["unit_number"])

        return X_scaled
