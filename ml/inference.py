"""Load the trained RUL artifact and run inference with conformal intervals and TreeSHAP contributions."""
import math
import os
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features import build_features

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = Path(os.environ.get("MODEL_PATH", ARTIFACT_DIR / "rul_model.joblib"))


class RulModel:
    def __init__(self, bundle: dict):
        self.bundle = bundle
        self.model = bundle["model"]
        self.features: list[str] = bundle["feature_names"]
        self.sensors: list[str] = bundle["sensors"]
        self.version: str = bundle["version"]
        self.conformal: dict = bundle["conformal"]
        self.feature_stats: dict = bundle["feature_stats"]
        self.sensor_stats: dict = bundle["sensor_stats"]

    def features_for(self, readings: pd.DataFrame) -> pd.DataFrame:
        return build_features(readings, self.sensors)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.clip(self.model.predict(X[self.features]), 0, None)

    def interval(self, pred: float) -> tuple[float, float]:
        """Mondrian split-conformal interval: residual quantile of the predicted-RUL bin."""
        edges, qs = self.conformal["bin_edges"], self.conformal["quantiles"]
        i = int(np.searchsorted(edges[1:-1], pred, side="right"))
        q = qs[i]
        return max(0.0, pred - q), pred + q

    def contributions(self, X: pd.DataFrame) -> pd.DataFrame:
        """Exact TreeSHAP values (LightGBM pred_contrib). Last column is the expected value."""
        c = self.model.predict(X[self.features], pred_contrib=True)
        return pd.DataFrame(c, columns=[*self.features, "_base"], index=X.index)

    def explain_row(self, X: pd.DataFrame, top: int = 8) -> list[dict]:
        row = self.contributions(X.tail(1)).iloc[0]
        vals = X.tail(1)[self.features].iloc[0]
        items = [
            {"feature": f, "value": float(vals[f]), "contribution": float(row[f])}
            for f in self.features
        ]
        items.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return items[:top]


@lru_cache(maxsize=1)
def load_model() -> RulModel:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model artifact not found at {MODEL_PATH}. Run `python manage.py train`.")
    return RulModel(joblib.load(MODEL_PATH))


def conformal_quantile(residuals: np.ndarray, alpha: float) -> float:
    n = len(residuals)
    k = min(n, math.ceil((n + 1) * (1 - alpha)))
    return float(np.sort(residuals)[k - 1])
