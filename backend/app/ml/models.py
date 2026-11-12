"""Baseline and gradient boosting models for Remaining Useful Life (RUL) estimation."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.pipelines.features import FeatureManifest


class NaiveBaselineModel:
    """Benchmark baseline model predicting the median capped RUL of training units."""

    def __init__(self) -> None:
        self.median_rul: float = 125.0
        self.lower_rul = 0.0
        self.upper_rul = 125.0
        self.manifest: FeatureManifest | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        manifest: FeatureManifest | None = None,
    ) -> "NaiveBaselineModel":
        self.manifest = manifest
        self.lower_rul, self.upper_rul = (float(v) for v in np.quantile(y, [0.05, 0.95]))
        self.median_rul = float(np.median(y))
        return self

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = len(X)
        preds = np.full(n, self.median_rul)
        lower = np.full(n, max(0.0, self.lower_rul))
        upper = np.full(n, self.upper_rul)
        return preds, lower, upper

    def save(self, filepath: str | Path) -> None:
        joblib.dump({"naive_model": self}, filepath)


class GradientBoostingRULModel:
    """Tabular Gradient Boosting model with nominal 90% quantile prediction intervals."""

    def __init__(
        self,
        learning_rate: float = 0.08,
        max_iter: int = 120,
        max_depth: int = 6,
        random_state: int = 42,
    ) -> None:
        self.learning_rate = learning_rate
        self.max_iter = max_iter
        self.max_depth = max_depth
        self.random_state = random_state

        # Primary point prediction model (least squares loss)
        self.point_model = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_depth=max_depth,
            random_state=random_state,
        )

        # Quantile models for 90% prediction intervals
        self.lower_model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.05,
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_depth=max_depth,
            random_state=random_state,
        )

        self.upper_model = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=0.95,
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_depth=max_depth,
            random_state=random_state,
        )

        self.manifest: FeatureManifest | None = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        manifest: FeatureManifest | None = None,
    ) -> "GradientBoostingRULModel":
        """Fits the point estimator and interval models on the training feature matrix."""
        self.manifest = manifest
        y_arr = np.asarray(y, dtype=float)
        X_arr = np.asarray(X, dtype=float)

        self.point_model.fit(X_arr, y_arr)
        self.lower_model.fit(X_arr, y_arr)
        self.upper_model.fit(X_arr, y_arr)

        return self

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Predicts RUL point estimates and lower/upper 90% prediction intervals.

        Returns:
            (predictions, lower_bounds, upper_bounds)
        """
        X_arr = np.asarray(X, dtype=float)
        preds = self.point_model.predict(X_arr)
        lower = self.lower_model.predict(X_arr)
        upper = self.upper_model.predict(X_arr)

        # Non-negative RUL constraint and logical interval bounds
        preds = np.maximum(0.0, preds)
        lower = np.maximum(0.0, np.minimum(lower, preds))
        upper = np.maximum(preds, upper)

        return preds, lower, upper

    def save(self, filepath: str | Path) -> None:
        """Persists the model bundle to disk."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "point_model": self.point_model,
            "lower_model": self.lower_model,
            "upper_model": self.upper_model,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "max_iter": self.max_iter,
                "max_depth": self.max_depth,
                "random_state": self.random_state,
            },
        }
        joblib.dump(bundle, path)

    @classmethod
    def load(cls, filepath: str | Path) -> "GradientBoostingRULModel":
        """Loads a model bundle from disk."""
        bundle = joblib.load(filepath)
        hp = bundle.get("hyperparameters", {})
        instance = cls(
            learning_rate=hp.get("learning_rate", 0.08),
            max_iter=hp.get("max_iter", 120),
            max_depth=hp.get("max_depth", 6),
            random_state=hp.get("random_state", 42),
        )
        instance.point_model = bundle["point_model"]
        instance.lower_model = bundle["lower_model"]
        instance.upper_model = bundle["upper_model"]
        if bundle.get("manifest"):
            instance.manifest = FeatureManifest.from_dict(bundle["manifest"])
        return instance


def load_rul_model(filepath: str | Path) -> GradientBoostingRULModel | NaiveBaselineModel:
    bundle = joblib.load(filepath)
    if "naive_model" in bundle:
        model = bundle["naive_model"]
        if not isinstance(model, NaiveBaselineModel):
            raise ValueError("Invalid naive model artifact")
        return model
    return GradientBoostingRULModel.load(filepath)
