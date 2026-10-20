"""AeroPulse TrustTwin: data-quality assessment + confidence-gated RUL prediction.

States: VALID (advisory use), DEGRADED (manual verification recommended), UNAVAILABLE (no estimate).
"""
import math
from datetime import datetime

import numpy as np
import pandas as pd

from ml.features import SLOPE_WINDOW
from ml.inference import RulModel

SEVERITY = {"pass": 0, "warn": 1, "fail": 2}
STATE = {0: "VALID", 1: "DEGRADED", 2: "UNAVAILABLE"}
TEMP_SENSORS = {"s1", "s2", "s3", "s4"}  # degR in the training schema


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def assess(readings: list[dict], now: datetime, model: RulModel, th: dict) -> dict:
    """readings: [{"cycle": int, "recorded_at": datetime, "values": {sensor: value}}], any order."""
    checks: list[dict] = []

    def check(cid, label, status, detail):
        checks.append({"id": cid, "label": label, "status": status, "detail": detail})

    base = {"model_version": model.version, "n_cycles": len(readings), "checks": checks,
            "rul": None, "rul_lower": None, "rul_upper": None, "evidence": [], "imputed": {}}
    if not readings:
        check("history", "Sensor history", "fail", "No sensor readings available for this engine.")
        return {**base, "state": "UNAVAILABLE", "summary": "No data: prediction withheld."}

    readings = sorted(readings, key=lambda r: r["cycle"])
    last = readings[-1]
    sensors = model.sensors
    stats = model.sensor_stats

    # 1. schema / missing fields, 2. invalid + implausible values (latest reading)
    raw = pd.DataFrame([{s: _num(r["values"].get(s)) for s in sensors} for r in readings], dtype=float)
    missing_latest = [s for s in sensors if s not in last["values"] or last["values"].get(s) is None]
    non_numeric = [s for s in sensors if s in last["values"] and last["values"][s] is not None
                   and _num(last["values"][s]) is None]
    implausible, unit_hints = [], []
    for s in sensors:
        v = raw[s].iloc[-1]
        st = stats[s]
        lo, hi = st["min"] - th["plausibility_sigma"] * st["std"], st["max"] + th["plausibility_sigma"] * st["std"]
        if not np.isnan(v) and not lo <= v <= hi:
            implausible.append(s)
            if s in TEMP_SENSORS and lo <= v * 1.8 <= hi:
                unit_hints.append(f"{s} looks like Kelvin (x1.8 fits the degR training range)")
    for s in implausible:
        raw.loc[raw.index[-1], s] = np.nan   # never feed an implausible value to the model

    if missing_latest:
        status = "fail" if len(missing_latest) > th["max_missing_sensors_degraded"] else "warn"
        check("missing", "Missing sensor fields", status,
              f"Latest reading lacks {', '.join(missing_latest)}; last valid values carried forward."
              if status == "warn" else f"{len(missing_latest)} model sensors missing ({', '.join(missing_latest)}).")
    else:
        check("missing", "Missing sensor fields", "pass", "All model sensors present in latest reading.")
    if non_numeric or implausible:
        detail = []
        if non_numeric:
            detail.append(f"non-numeric: {', '.join(non_numeric)}")
        if implausible:
            detail.append(f"outside physical plausibility bounds: {', '.join(implausible)}")
        if unit_hints:
            detail.append("possible unit mismatch - " + "; ".join(unit_hints))
        check("invalid", "Invalid / implausible values", "fail", "; ".join(detail))
    else:
        check("invalid", "Invalid / implausible values", "pass", "All values numeric and within plausible bounds.")
    if unit_hints:
        check("units", "Units consistency", "fail", "; ".join(unit_hints))
    else:
        check("units", "Units consistency", "pass", "Values consistent with training units (degR, psia, rpm).")

    # 3. large step deviation vs recent median (latest reading)
    spikes = []
    if len(raw) >= 4:
        prev = raw.iloc[-11:-1]
        for s in sensors:
            v = raw[s].iloc[-1]
            if np.isnan(v) or prev[s].isna().all():
                continue
            z = abs(v - prev[s].median()) / max(stats[s]["step_std"], 1e-9)
            if z > th["spike_sigma"]:
                spikes.append(f"{s} ({z:.0f} sigma)")
    check("deviation", "Unusual sensor deviation", "warn" if spikes else "pass",
          f"Step change vs recent median: {', '.join(spikes)}." if spikes else "No abnormal step changes.")

    # 4. staleness
    age_h = (now - last["recorded_at"]).total_seconds() / 3600
    st_status = ("fail" if age_h > th["stale_unavailable_hours"] else
                 "warn" if age_h > th["stale_degraded_hours"] else "pass")
    check("stale", "Data freshness", st_status, f"Last reading {age_h:.0f} h old "
          f"(degraded > {th['stale_degraded_hours']} h, unavailable > {th['stale_unavailable_hours']} h).")

    # 5. history length
    n = len(readings)
    h_status = ("fail" if n < th["min_history_cycles"] else
                "warn" if n < th["min_history_valid_cycles"] else "pass")
    check("history", "History length", h_status,
          f"{n} cycles (need {th['min_history_valid_cycles']} for full trend features).")

    # impute (forward fill) then build causal features on the cleaned stream
    filled = raw.ffill()
    unrecoverable = [s for s in sensors if np.isnan(filled[s].iloc[-1])]
    imputed = {s: float(filled[s].iloc[-1]) for s in sensors if np.isnan(raw[s].iloc[-1]) and s not in unrecoverable}
    base["imputed"] = imputed
    if unrecoverable:
        check("impute", "Imputation", "fail", f"No valid history to impute {', '.join(unrecoverable)}.")

    severity = max(SEVERITY[c["status"]] for c in checks)
    if severity < 2:
        df = filled.assign(unit=0, cycle=[r["cycle"] for r in readings])
        # The last row's features only depend on the last SLOPE_WINDOW readings (causal windows).
        X = model.features_for(df.tail(SLOPE_WINDOW)).tail(1)
        fs = model.feature_stats
        out = [f for f in model.features if not fs[f]["p005"] <= X[f].iloc[0] <= fs[f]["p995"]]
        frac = len(out) / len(model.features)
        o_status = ("fail" if frac > th["ood_fraction_unavailable"] else
                    "warn" if frac > th["ood_fraction_degraded"] else "pass")
        check("ood", "Training-distribution check", o_status,
              f"{len(out)}/{len(model.features)} features outside training p0.5-p99.5"
              + (f" ({', '.join(out[:6])}{'...' if len(out) > 6 else ''})." if out else "."))
        severity = max(severity, SEVERITY[o_status])
        if severity < 2:
            rul = float(model.predict(X)[0])
            lo, hi = model.interval(rul)
            meta = model.bundle["sensor_meta"]
            evidence = model.explain_row(X)
            for e in evidence:
                s = e["feature"].split("_")[0]
                e["sensor"] = meta.get(s, ("cycle", "Engine operating cycles", "cycles"))[0] if s != "cycle" else "cycle"
            base.update(rul=rul, rul_lower=lo, rul_upper=hi, evidence=evidence)
    else:
        checks.append({"id": "ood", "label": "Training-distribution check", "status": "skipped",
                       "detail": "Not evaluated: input failed earlier checks."})

    state = STATE[severity]
    reasons = [c["label"] + ": " + c["detail"] for c in checks if c["status"] in ("warn", "fail")]
    summary = {"VALID": "Inputs passed all checks; prediction accepted for advisory evaluation.",
               "DEGRADED": "Input quality questionable; manual verification recommended. "
                           "Interval coverage is not guaranteed for degraded inputs.",
               "UNAVAILABLE": "Prediction withheld: inputs cannot support a responsible estimate."}[state]
    return {**base, "state": state, "summary": summary, "reasons": reasons, "cycle": last["cycle"],
            "last_recorded_at": last["recorded_at"].isoformat(), "data_age_hours": round(age_h, 1)}
