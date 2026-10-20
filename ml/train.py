"""Reproducible RUL training on NASA C-MAPSS FD001.

    python -m ml.train            # from repo root

Protocol (engine-grouped, no row-level leakage):
  * 100 training engines -> 65 fit / 15 conformal calibration / 20 hold-out (run-to-failure)
  * model selection: 5-fold GroupKFold over the 65 fit engines
  * final test: official test_FD001 (last observed cycle per engine) vs RUL_FD001
"""
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from ml import data  # noqa: E402
from ml.features import SLOPE_WINDOW, WINDOW, build_features, feature_names, select_sensors  # noqa: E402
from ml.inference import ARTIFACT_DIR, conformal_quantile  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent / "evaluation"

CONFIG: dict[str, Any] = {
    "subset": "FD001",
    "seed": 42,
    "rul_cap": 125,              # piecewise-linear target (Heimes 2008 convention)
    "split": {"fit": 65, "calibration": 15, "holdout": 20},
    "cv_folds": 5,
    "alpha": 0.10,               # 90% conformal intervals
    "conformal_bin_edges": [0, 50, 100, 1e9],
    "window": WINDOW,
    "slope_window": SLOPE_WINDOW,
    "candidates": {
        "lgbm_a": {"n_estimators": 600, "learning_rate": 0.03, "num_leaves": 31, "min_child_samples": 40,
                   "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8, "reg_lambda": 1.0},
        "lgbm_b": {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 15, "min_child_samples": 80,
                   "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.7, "reg_lambda": 5.0},
    },
}


def metrics(y, p) -> dict:
    d = np.asarray(p, float) - np.asarray(y, float)
    # PHM08 asymmetric score: late predictions (d > 0) are penalised more.
    score = float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))
    return {"mae": float(np.mean(np.abs(d))), "rmse": float(np.sqrt(np.mean(d * d))),
            "bias": float(np.mean(d)), "phm08_score": score, "n": int(len(d))}


def make_model(name: str, seed: int):
    if name == "mean_baseline":
        return None
    if name == "ridge_baseline":
        return make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    return lgb.LGBMRegressor(**CONFIG["candidates"][name], random_state=seed, deterministic=True,
                             force_row_wise=True, n_jobs=4, verbose=-1)


def fit_predict(name, Xtr, ytr, Xte, seed):
    if name == "mean_baseline":
        return np.full(len(Xte), float(np.mean(ytr))), None
    m = make_model(name, seed)
    m.fit(Xtr, ytr)
    return np.clip(m.predict(Xte), 0, None), m


def coverage(y, lo, hi) -> float:
    y = np.asarray(y)
    return float(np.mean((y >= lo) & (y <= hi)))


def main() -> dict:
    t0 = time.time()
    cfg, seed = CONFIG, CONFIG["seed"]
    train_raw, test_raw, test_rul = data.load_fd(cfg["subset"])
    archive = data.DATA_DIR / "cmapss.zip"
    dataset_sha = data.sha256(archive) if archive.exists() else data.DATASET_SHA256

    units = np.random.default_rng(seed).permutation(sorted(train_raw["unit"].unique()))
    n_fit, n_cal = cfg["split"]["fit"], cfg["split"]["calibration"]
    fit_u, cal_u, hold_u = units[:n_fit], units[n_fit:n_fit + n_cal], units[n_fit + n_cal:]
    assert not (set(fit_u) & set(cal_u) | set(fit_u) & set(hold_u) | set(cal_u) & set(hold_u))

    fit_rows = train_raw[train_raw.unit.isin(fit_u)]
    sensors = select_sensors(fit_rows, data.SENSORS)          # fitted on fit engines only
    feats = feature_names(sensors)

    labelled = data.add_rul_target(train_raw, cfg["rul_cap"])
    F = build_features(labelled, sensors)
    F_fit, F_cal, F_hold = (F[F.unit.isin(u)].reset_index(drop=True) for u in (fit_u, cal_u, hold_u))

    # ---- model selection: engine-grouped CV on fit engines --------------------------------
    cv = {}
    gkf = GroupKFold(n_splits=cfg["cv_folds"])
    for name in ["mean_baseline", "ridge_baseline", *cfg["candidates"]]:
        oof = np.zeros(len(F_fit))
        for tr, va in gkf.split(F_fit, groups=F_fit.unit):
            assert not set(F_fit.unit.iloc[tr]) & set(F_fit.unit.iloc[va])  # no engine in both
            oof[va], _ = fit_predict(name, F_fit.loc[tr, feats], F_fit.rul[tr], F_fit.loc[va, feats], seed)
        cv[name] = metrics(F_fit.rul, oof)
        print(f"CV {name:15s} RMSE={cv[name]['rmse']:.2f} MAE={cv[name]['mae']:.2f}")
    best = min(cv, key=lambda k: cv[k]["rmse"])
    print("selected:", best)

    # ---- final fit + conformal calibration -----------------------------------------------
    _, model = fit_predict(best, F_fit[feats], F_fit.rul, F_fit[feats].head(1), seed)
    ridge = make_model("ridge_baseline", seed).fit(F_fit[feats], F_fit.rul)
    mean_rul = float(F_fit.rul.mean())

    cal_pred = np.clip(model.predict(F_cal[feats]), 0, None)
    cal_res = np.abs(F_cal.rul.to_numpy() - cal_pred)
    edges = cfg["conformal_bin_edges"]
    bin_idx = np.searchsorted(edges[1:-1], cal_pred, side="right")
    quantiles, bin_counts = [], []
    for b in range(len(edges) - 1):
        r = cal_res[bin_idx == b]
        bin_counts.append(int(len(r)))
        quantiles.append(conformal_quantile(r, cfg["alpha"]) if len(r) >= 30
                         else conformal_quantile(cal_res, cfg["alpha"]))
    conformal = {"method": "Mondrian split-conformal (bins on predicted RUL)", "alpha": cfg["alpha"],
                 "bin_edges": edges, "quantiles": quantiles, "bin_counts": bin_counts,
                 "calibration_engines": [int(u) for u in cal_u], "n_calibration_rows": int(len(cal_res))}

    def intervals(pred):
        i = np.searchsorted(edges[1:-1], pred, side="right")
        q = np.asarray(quantiles)[i]
        return np.maximum(0, pred - q), pred + q

    # ---- official test set: last observed cycle per engine --------------------------------
    T = build_features(test_raw, sensors)
    T_last = T.groupby("unit").tail(1).set_index("unit").sort_index()
    y_true = test_rul.loc[T_last.index].to_numpy(float)
    y_cap = np.minimum(y_true, cfg["rul_cap"])
    p_best = np.clip(model.predict(T_last[feats]), 0, None)
    p_ridge = np.clip(ridge.predict(T_last[feats]), 0, None)
    lo, hi = intervals(p_best)
    test_eval = {
        "protocol": "Official test_FD001: prediction at last observed cycle of each of 100 engines vs RUL_FD001.",
        "selected_model": metrics(y_true, p_best),
        "selected_model_vs_capped_truth": metrics(y_cap, p_best),
        "ridge_baseline": metrics(y_true, p_ridge),
        "mean_baseline": metrics(y_true, np.full(len(y_true), mean_rul)),
        "interval_coverage_capped_truth": coverage(y_cap, lo, hi),
        "interval_coverage_raw_truth": coverage(y_true, lo, hi),
        "mean_interval_width": float(np.mean(hi - lo)),
    }

    # ---- hold-out run-to-failure engines (never used for fit or calibration) ---------------
    p_hold = np.clip(model.predict(F_hold[feats]), 0, None)
    hlo, hhi = intervals(p_hold)
    near = F_hold.rul.to_numpy() <= 50
    hold_eval = {
        "protocol": "20 hold-out training engines, every cycle, target capped at 125.",
        "selected_model": metrics(F_hold.rul, p_hold),
        "selected_model_rul_le_50": metrics(F_hold.rul[near], p_hold[near]),
        "interval_coverage": coverage(F_hold.rul, hlo, hhi),
        "interval_coverage_rul_le_50": coverage(F_hold.rul[near], hlo[near], hhi[near]),
        "engines": [int(u) for u in hold_u],
    }

    # ---- explanations: SHAP TreeExplainer (global) + equivalence with LightGBM pred_contrib -
    shap_info = {}
    if best.startswith("lgbm"):
        import shap
        sample = F_fit[feats].sample(2000, random_state=seed)
        sv = shap.TreeExplainer(model).shap_values(sample)
        contrib = model.predict(sample, pred_contrib=True)[:, :-1]
        shap_info = {
            "method": "shap.TreeExplainer on 2000 fit rows; runtime uses LightGBM pred_contrib (TreeSHAP)",
            "max_abs_diff_shap_vs_pred_contrib": float(np.max(np.abs(sv - contrib))),
            "mean_abs_shap": [{"feature": f, "value": v} for f, v in
                              sorted(zip(feats, np.abs(sv).mean(axis=0).tolist()), key=lambda fv: fv[1], reverse=True)],
        }
        shap.summary_plot(sv, sample, show=False, max_display=15)
        plt.tight_layout()
        plt.savefig(EVAL_DIR / "shap_summary.png", dpi=110)
        plt.close("all")

    # ---- distribution stats for TrustTwin OOD / plausibility checks (fit engines only) -----
    feature_stats = {f: {"p005": float(F_fit[f].quantile(0.005)), "p995": float(F_fit[f].quantile(0.995)),
                         "mean": float(F_fit[f].mean()), "std": float(F_fit[f].std())} for f in feats}
    sensor_stats = {}
    for s in sensors:
        col = fit_rows[s]
        step = fit_rows.groupby("unit")[s].diff().dropna()
        sensor_stats[s] = {"min": float(col.min()), "max": float(col.max()), "mean": float(col.mean()),
                           "std": float(col.std()), "step_std": float(step.std())}

    cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode() + dataset_sha.encode()).hexdigest()[:8]
    version = f"fd001-{best}-{cfg_hash}"
    provenance = {"dataset": "NASA C-MAPSS Turbofan Engine Degradation Simulation (FD001)",
                  "source_url": data.DATASET_URL, "archive_sha256": dataset_sha,
                  "note": "Simulated commercial turbofan data (Saxena et al., 2008). Not military data."}
    report = {
        "model_version": version, "selected_model": best, "trained_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "training_seconds": round(time.time() - t0, 1), "config": cfg, "provenance": provenance,
        "environment": {"python": platform.python_version(), "lightgbm": lgb.__version__},
        "sensors_used": sensors, "sensors_dropped": [s for s in data.SENSORS if s not in sensors],
        "n_features": len(feats), "n_fit_rows": int(len(F_fit)),
        "split_engines": {"fit": [int(u) for u in fit_u], "calibration": [int(u) for u in cal_u],
                          "holdout": [int(u) for u in hold_u]},
        "cv": cv, "test": test_eval, "holdout": hold_eval, "conformal": conformal, "shap": shap_info,
        "test_predictions": [{"unit": int(u), "true_rul": float(t), "pred": float(p), "lo": float(a), "hi": float(b),
                              "ridge": float(r)} for u, t, p, a, b, r in
                             zip(T_last.index, y_true, p_best, lo, hi, p_ridge)],
    }

    # Native Booster: inference needs only lightgbm (no scikit-learn on the server).
    bundle = {"model": getattr(model, "booster_", model), "feature_names": feats, "sensors": sensors, "version": version,
              "conformal": conformal, "feature_stats": feature_stats, "sensor_stats": sensor_stats,
              "rul_cap": cfg["rul_cap"], "provenance": provenance, "window": WINDOW, "slope_window": SLOPE_WINDOW,
              "sensor_meta": {s: data.SENSOR_META[s] for s in sensors}}
    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(bundle, ARTIFACT_DIR / "rul_model.joblib", compress=3)
    (ARTIFACT_DIR / "feature_schema.json").write_text(json.dumps(
        {"model_version": version, "sensors": {s: dict(zip(["symbol", "description", "unit"], data.SENSOR_META[s]))
                                               for s in sensors},
         "features": feats, "window": WINDOW, "slope_window": SLOPE_WINDOW}, indent=2))
    (ARTIFACT_DIR / "evaluation_report.json").write_text(json.dumps(report, indent=2))
    # Hold-out run-to-failure trajectories feed the synthetic demo fleet and simulator.
    train_raw[train_raw.unit.isin(hold_u)].to_csv(ARTIFACT_DIR / "holdout_trajectories.csv.gz", index=False)

    _plots(y_true, p_best, lo, hi, p_ridge, cv, shap_info)
    print(json.dumps({k: report["test"][k] for k in ("selected_model", "ridge_baseline", "interval_coverage_capped_truth")}, indent=1))
    print("version:", version, f"({report['training_seconds']}s)")
    return report


def _plots(y, p, lo, hi, p_ridge, cv, shap_info):
    EVAL_DIR.mkdir(exist_ok=True)
    order = np.argsort(y)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.fill_between(range(len(y)), lo[order], hi[order], alpha=0.25, label="90% conformal interval")
    ax.plot(y[order], "k.", label="true RUL")
    ax.plot(p[order], "b.", label="predicted RUL")
    ax.set(xlabel="test engine (sorted by true RUL)", ylabel="RUL (cycles)", title="FD001 test set")
    ax.legend()
    fig.tight_layout(); fig.savefig(EVAL_DIR / "test_predictions.png", dpi=110); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(p - y, bins=25, alpha=0.7, label="LightGBM")
    ax.hist(p_ridge - y, bins=25, alpha=0.5, label="Ridge baseline")
    ax.set(xlabel="prediction error (cycles, + = late)", ylabel="engines", title="Error distribution (test)")
    ax.legend(); fig.tight_layout(); fig.savefig(EVAL_DIR / "error_distribution.png", dpi=110); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3))
    names = list(cv)
    ax.barh(names, [cv[n]["rmse"] for n in names])
    ax.set(xlabel="CV RMSE (cycles, capped target)", title="Engine-grouped 5-fold CV")
    fig.tight_layout(); fig.savefig(EVAL_DIR / "cv_comparison.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    main()
