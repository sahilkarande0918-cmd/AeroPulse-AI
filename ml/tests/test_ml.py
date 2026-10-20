"""ML pipeline checks on the real NASA C-MAPSS FD001 data (mandatory scenarios 1-5 + reproducibility)."""
import json

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from ml import data
from ml.features import build_features, feature_names, select_sensors
from ml.inference import ARTIFACT_DIR, load_model
from ml.train import CONFIG, metrics

REPORT = json.loads((ARTIFACT_DIR / "evaluation_report.json").read_text())


@pytest.fixture(scope="module")
def fd001():
    return data.load_fd("FD001")


def test_dataset_parsing(fd001):  # scenario 1
    train, test, rul = fd001
    assert list(train.columns) == data.COLUMNS and len(data.COLUMNS) == 26
    assert train.unit.nunique() == 100 and test.unit.nunique() == 100 and len(rul) == 100
    assert len(train) == 20631 and len(test) == 13096
    assert not train.isna().any().any()


def test_model_trains_on_real_data(fd001):  # scenario 2
    train, _, _ = fd001
    lab = data.add_rul_target(train, 125)
    sensors = select_sensors(lab[lab.unit <= 60], data.SENSORS)
    F = build_features(lab, sensors)
    feats = feature_names(sensors)
    tr, va = F[F.unit <= 60], F[F.unit > 80]
    m = lgb.LGBMRegressor(n_estimators=150, random_state=0, verbose=-1, deterministic=True, force_row_wise=True).fit(tr[feats], tr.rul)
    model_rmse = metrics(va.rul, m.predict(va[feats]))["rmse"]
    mean_rmse = metrics(va.rul, np.full(len(va), tr.rul.mean()))["rmse"]
    assert model_rmse < 0.6 * mean_rmse
    assert REPORT["n_fit_rows"] > 10000 and REPORT["provenance"]["archive_sha256"] == data.DATASET_SHA256


def test_saved_model_loads_and_infers(fd001):  # scenario 3
    _, test, _ = fd001
    model = load_model()
    X = model.features_for(test[test.unit == 1]).tail(1)
    pred = float(model.predict(X)[0])
    lo, hi = model.interval(pred)
    assert np.isfinite(pred) and lo <= pred <= hi
    contrib = model.contributions(X)
    assert np.isclose(contrib.sum(axis=1).iloc[0], model.model.predict(X[model.features])[0], atol=1e-6)


def test_reported_test_metrics_match_real_predictions(fd001):  # scenario 4
    _, test, rul = fd001
    model = load_model()
    T = model.features_for(test).groupby("unit").tail(1).set_index("unit").sort_index()
    preds = model.predict(T)
    m = metrics(rul.loc[T.index].to_numpy(), preds)
    assert m["rmse"] == pytest.approx(REPORT["test"]["selected_model"]["rmse"], abs=1e-6)
    assert m["mae"] == pytest.approx(REPORT["test"]["selected_model"]["mae"], abs=1e-6)
    assert REPORT["test"]["selected_model"]["rmse"] < REPORT["test"]["ridge_baseline"]["rmse"]


def test_no_engine_leakage_between_splits():  # scenario 5
    s = REPORT["split_engines"]
    fit, cal, hold = set(s["fit"]), set(s["calibration"]), set(s["holdout"])
    assert not (fit & cal or fit & hold or cal & hold)
    assert len(fit | cal | hold) == 100
    assert set(REPORT["conformal"]["calibration_engines"]) == cal


def test_features_are_causal():  # scenario 5: no future readings in an inference window
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"unit": 1, "cycle": np.arange(1, 61), "s2": rng.normal(642, 0.5, 60), "s3": rng.normal(1590, 5, 60)})
    full = build_features(df, ["s2", "s3"])
    for t in (5, 20, 45):
        part = build_features(df.iloc[:t], ["s2", "s3"])
        pd.testing.assert_series_equal(part.iloc[-1], full.iloc[t - 1], check_names=False)


def test_training_is_reproducible(fd001):
    train, _, _ = fd001
    lab = data.add_rul_target(train[train.unit <= 30], 125)
    sensors = select_sensors(lab, data.SENSORS)
    F = build_features(lab, sensors)
    feats = feature_names(sensors)
    p = [lgb.LGBMRegressor(**CONFIG["candidates"]["lgbm_b"], random_state=42, deterministic=True, force_row_wise=True,
                           n_jobs=4, verbose=-1).fit(F[feats], F.rul).predict(F[feats].head(50)) for _ in range(2)]
    np.testing.assert_array_equal(p[0], p[1])


def test_inference_window_matches_full_history(fd001):
    """Inference builds features on the last SLOPE_WINDOW readings only; the last row must be identical."""
    from ml.features import SLOPE_WINDOW
    _, test, _ = fd001
    model = load_model()
    g = test[test.unit == 31]
    full = model.features_for(g).tail(1).drop(columns="unit").reset_index(drop=True)
    tail = model.features_for(g.tail(SLOPE_WINDOW)).tail(1).drop(columns="unit").reset_index(drop=True)
    pd.testing.assert_frame_equal(full, tail)


def test_artifact_needs_no_sklearn():
    import lightgbm as lgb
    assert isinstance(load_model().model, lgb.Booster)


def test_benchmark_report_covers_all_subsets():
    rep = json.loads((ARTIFACT_DIR / "benchmark_report.json").read_text())
    res = {r["subset"]: r for r in rep["results"]}
    assert set(res) == {"FD001", "FD002", "FD003", "FD004"}
    assert all(r["lightgbm"]["rmse"] < r["ridge"]["rmse"] for r in res.values())
    assert res["FD002"]["condition_normalised"] and not res["FD001"]["condition_normalised"]
