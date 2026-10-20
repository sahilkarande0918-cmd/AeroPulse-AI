"""Evaluation-only benchmark across all four C-MAPSS subsets (the deployed model remains FD001).

    python -m ml.benchmark        -> ml/artifacts/benchmark_report.json

Same protocol for every subset: engines split by unit (80 % fit / 20 % conformal calibration, seed 42), causal
features, LightGBM (config "lgbm_a" from ml.train) vs Ridge, Mondrian conformal 90 % intervals, scored on the
official test set at each engine's last observed cycle. FD002/FD004 mix six operating conditions, so each sensor is
standardised per condition (statistics from fit engines only) before feature engineering.
"""
import json
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml import data
from ml.features import build_features, feature_names, select_sensors
from ml.inference import ARTIFACT_DIR, conformal_quantile
from ml.train import CONFIG, metrics

SUBSETS = {"FD001": "1 condition, 1 fault mode", "FD002": "6 conditions, 1 fault mode",
           "FD003": "1 condition, 2 fault modes", "FD004": "6 conditions, 2 fault modes"}


def condition(df: pd.DataFrame) -> pd.Series:
    return df["setting_1"].round().astype(int)


def normalise_by_condition(frames: list[pd.DataFrame], fit: pd.DataFrame) -> list[pd.DataFrame]:
    stats = fit.assign(cond=condition(fit)).groupby("cond")[data.SENSORS].agg(["mean", "std"])
    out = []
    for f in frames:
        f = f.copy()
        cond = condition(f)
        for s in data.SENSORS:
            mu, sd = cond.map(stats[(s, "mean")]), cond.map(stats[(s, "std")]).replace(0, np.nan)
            f[s] = ((f[s] - mu) / sd).fillna(0.0)
        out.append(f)
    return out


def run_subset(subset: str, seed: int = 42) -> dict:
    t0 = time.time()
    train, test, rul = data.load_fd(subset)
    units = np.random.default_rng(seed).permutation(sorted(train.unit.unique()))
    n_fit = int(len(units) * 0.8)
    fit_u, cal_u = set(units[:n_fit]), set(units[n_fit:])
    multi = condition(train).nunique() > 1
    if multi:
        train, test = normalise_by_condition([train, test], train[train.unit.isin(fit_u)])
    sensors = select_sensors(train[train.unit.isin(fit_u)], data.SENSORS)
    feats = feature_names(sensors)
    F = build_features(data.add_rul_target(train, CONFIG["rul_cap"]), sensors)
    F_fit, F_cal = F[F.unit.isin(fit_u)], F[F.unit.isin(cal_u)]

    model = lgb.LGBMRegressor(**CONFIG["candidates"]["lgbm_a"], random_state=seed, deterministic=True,
                              force_row_wise=True, n_jobs=4, verbose=-1).fit(F_fit[feats], F_fit.rul)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=1.0)).fit(F_fit[feats], F_fit.rul)

    edges = CONFIG["conformal_bin_edges"]
    cal_pred = np.clip(model.predict(F_cal[feats]), 0, None)
    res = np.abs(F_cal.rul.to_numpy() - cal_pred)
    b = np.searchsorted(edges[1:-1], cal_pred, side="right")
    qs = [conformal_quantile(res[b == i], CONFIG["alpha"]) if (b == i).sum() >= 30 else conformal_quantile(res, CONFIG["alpha"])
          for i in range(len(edges) - 1)]

    T = build_features(test, sensors).groupby("unit").tail(1).set_index("unit").sort_index()
    y = rul.loc[T.index].to_numpy(float)
    p = np.clip(model.predict(T[feats]), 0, None)
    q = np.asarray(qs)[np.searchsorted(edges[1:-1], p, side="right")]
    lo, hi = np.maximum(0, p - q), p + q
    y_cap = np.minimum(y, CONFIG["rul_cap"])
    return {
        "subset": subset, "description": SUBSETS[subset], "condition_normalised": bool(multi),
        "train_engines": len(units), "test_engines": int(len(T)), "sensors_used": sensors,
        "lightgbm": metrics(y, p), "ridge": metrics(y, np.clip(ridge.predict(T[feats]), 0, None)),
        "interval_coverage_capped_truth": float(np.mean((y_cap >= lo) & (y_cap <= hi))),
        "mean_interval_width": float(np.mean(hi - lo)), "seconds": round(time.time() - t0, 1),
    }


def main() -> dict:
    results = [run_subset(s) for s in SUBSETS]
    report = {"protocol": __doc__.strip().splitlines()[0], "config": "lgbm_a, rul_cap 125, alpha 0.10, seed 42",
              "note": "Evaluation only; the application serves the FD001 model trained by ml.train.",
              "results": results}
    (ARTIFACT_DIR / "benchmark_report.json").write_text(json.dumps(report, indent=2))
    for r in results:
        print(f"{r['subset']} ({r['description']}): LightGBM RMSE {r['lightgbm']['rmse']:.2f} MAE {r['lightgbm']['mae']:.2f} | "
              f"Ridge RMSE {r['ridge']['rmse']:.2f} | coverage {r['interval_coverage_capped_truth']:.2f} | {r['seconds']} s")
    return report


if __name__ == "__main__":
    main()
