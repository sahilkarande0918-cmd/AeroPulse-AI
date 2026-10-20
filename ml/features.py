"""Causal feature engineering shared by training and backend inference.

Every feature at cycle t uses only readings at cycles <= t of the same engine,
so the same function serves training rows and live inference (no future leakage).
"""
import numpy as np
import pandas as pd

WINDOW = 10          # rolling mean/std window (cycles)
SLOPE_WINDOW = 20    # trend window (cycles)


def select_sensors(train: pd.DataFrame, sensors: list[str], min_rel_std: float = 1e-4) -> list[str]:
    """Drop constant / near-constant sensors, judged on training data only."""
    keep = []
    for s in sensors:
        col = train[s]
        if col.std() / (abs(col.mean()) + 1e-9) > min_rel_std and col.nunique() > 2:
            keep.append(s)
    return keep


def feature_names(sensors: list[str]) -> list[str]:
    names = ["cycle"]
    for s in sensors:
        names += [s, f"{s}_mean{WINDOW}", f"{s}_std{WINDOW}", f"{s}_slope{SLOPE_WINDOW}"]
    return names


def build_features(df: pd.DataFrame, sensors: list[str]) -> pd.DataFrame:
    """Rows must be (unit, cycle) readings. Returns one feature row per input row."""
    df = df.sort_values(["unit", "cycle"]).reset_index(drop=True)
    g = df.groupby("unit", sort=False)
    out = {"unit": df["unit"].to_numpy(), "cycle": df["cycle"].to_numpy(dtype=float)}
    t = df["cycle"].astype(float)
    tm = g["cycle"].transform(lambda c: c.astype(float).rolling(SLOPE_WINDOW, min_periods=2).mean())
    tt = (t * t).groupby(df["unit"]).transform(lambda c: c.rolling(SLOPE_WINDOW, min_periods=2).mean())
    var_t = tt - tm * tm
    for s in sensors:
        x = df[s].astype(float)
        gx = x.groupby(df["unit"])
        out[s] = x.to_numpy()
        out[f"{s}_mean{WINDOW}"] = gx.transform(lambda c: c.rolling(WINDOW, min_periods=1).mean()).to_numpy()
        out[f"{s}_std{WINDOW}"] = gx.transform(lambda c: c.rolling(WINDOW, min_periods=2).std()).fillna(0).to_numpy()
        xm = gx.transform(lambda c: c.rolling(SLOPE_WINDOW, min_periods=2).mean())
        tx = (t * x).groupby(df["unit"]).transform(lambda c: c.rolling(SLOPE_WINDOW, min_periods=2).mean())
        slope = (tx - tm * xm) / var_t.replace(0, np.nan)
        out[f"{s}_slope{SLOPE_WINDOW}"] = slope.fillna(0).to_numpy()
    feats = pd.DataFrame(out)
    for extra in ("rul",):
        if extra in df:
            feats[extra] = df[extra].to_numpy()
    return feats


if __name__ == "__main__":
    # Self-check: features at cycle t must not change when future rows are appended.
    rng = np.random.default_rng(0)
    full = pd.DataFrame({"unit": 1, "cycle": np.arange(1, 41), "s2": rng.normal(642, 0.5, 40)})
    a = build_features(full.iloc[:25], ["s2"]).iloc[-1]
    b = build_features(full, ["s2"]).iloc[24]
    assert np.allclose(a.drop("unit").to_numpy(float), b.drop("unit").to_numpy(float))
    print("causal feature check ok")
