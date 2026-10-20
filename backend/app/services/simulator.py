"""Deterministic fleet maintenance digital twin (SIMULATED) for policy comparison.

Both policies replay the *same* engine trajectories (real C-MAPSS hold-out run-to-failure engines,
never used for model fitting or calibration), the same replacement sequence, sensor dropouts,
technician absences and spare-part deliveries, all drawn up-front from one seed.

Policy A (reactive): fly until the engine reaches end of life (failure), then corrective repair.
Policy B (predictive, human-reviewed): daily trained-model prediction gated by TrustTwin; low
lower-bound RUL -> recommendation -> reviewed after a delay -> planned replacement when crew and
parts allow. Degraded inputs trigger a verification inspection instead of an automatic action.
"""
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from ml.inference import ARTIFACT_DIR, load_model

LABEL = "Results from a simulated scenario, not demonstrated real-world fleet improvements."


@dataclass
class SimParams:
    seed: int = 2026
    days: int = 120
    n_aircraft: int = 10
    engines_per_aircraft: int = 2
    cycles_per_day: int = 2
    crews: int = 2                    # concurrent maintenance jobs per day
    spare_engines: int = 4            # initial replacement-module stock
    resupply_every_days: int = 14
    resupply_qty: int = 3
    part_delay_prob: float = 0.3      # chance a resupply slips
    part_delay_days: int = 10
    dropout_prob: float = 0.02        # per engine-day sensor dropout -> DEGRADED input
    absence_prob: float = 0.05        # per crew-day technician absence
    review_delay_days: int = 1        # human review of a recommendation
    planned_days: int = 2             # planned module replacement
    corrective_days: int = 5          # unplanned removal after failure
    inspection_days: int = 1          # sensor/borescope verification for degraded inputs
    trigger_lower_bound: int = 25     # cycles: plan replacement when interval lower bound <= this
    hold_lower_bound: int = 6         # cycles: hold aircraft (stop flying) awaiting maintenance


@lru_cache(maxsize=1)
def trajectory_table() -> dict[int, pd.DataFrame]:
    """Per hold-out engine: true RUL plus model prediction/interval at every cycle (computed once)."""
    model = load_model()
    raw = pd.read_csv(ARTIFACT_DIR / "holdout_trajectories.csv.gz")
    out = {}
    for unit, g in raw.groupby("unit"):
        X = model.features_for(g)
        pred = model.predict(X)
        lo = np.array([model.interval(p)[0] for p in pred])
        out[int(str(unit))] = pd.DataFrame({"cycle": g["cycle"].to_numpy(), "pred": pred, "lo": lo,
                                       "true_rul": g["cycle"].max() - g["cycle"].to_numpy()})
    return out


def _events(p: SimParams, units: list[int], lengths: dict[int, int]):
    rng = np.random.default_rng(p.seed)
    n_eng = p.n_aircraft * p.engines_per_aircraft
    # Replacement queue per engine slot: (unit, starting cycle). Initial engines start part-way through life.
    queue = []
    for _ in range(n_eng):
        seq = []
        for k in range(12):
            u = int(rng.choice(units))
            start = int(rng.integers(1, int(lengths[u] * 0.7))) if k == 0 else 1
            seq.append((u, start))
        queue.append(seq)
    dropouts = rng.random((p.days, n_eng)) < p.dropout_prob
    absences = (rng.random((p.days, p.crews)) < p.absence_prob).sum(axis=1)
    deliveries: dict[int, int] = {}
    for d in range(p.resupply_every_days, p.days, p.resupply_every_days):
        slip = p.part_delay_days if rng.random() < p.part_delay_prob else 0
        if d + slip < p.days:
            deliveries[d + slip] = deliveries.get(d + slip, 0) + p.resupply_qty
    return queue, dropouts, absences, deliveries


def run_policy(policy: str, p: SimParams) -> dict:
    table = trajectory_table()
    units = sorted(table)
    lengths = {u: int(table[u]["cycle"].max()) for u in units}
    queue, dropouts, absences, deliveries = _events(p, units, lengths)
    n_eng = p.n_aircraft * p.engines_per_aircraft
    eng = [{"slot": i, "k": 0, "unit": queue[i][0][0], "cycle": queue[i][0][1], "failed": False,
            "held": False, "rec_day": None, "queued": None, "maint_until": -1} for i in range(n_eng)]
    stock = p.spare_engines
    jobs: list[dict] = []          # waiting maintenance jobs
    m = {"failures": 0, "planned_replacements": 0, "inspections": 0, "degraded_predictions": 0,
         "recommendations": 0, "part_shortage_job_days": 0, "crew_shortage_job_days": 0,
         "delayed_jobs": 0, "wasted_life_cycles": 0, "unresolved_at_end": 0}
    availability = []

    def aircraft_of(i):
        return i // p.engines_per_aircraft

    for day in range(p.days):
        stock += deliveries.get(day, 0)
        # 1. start waiting jobs in priority order (corrective first), limited by crews and parts
        crews = max(0, p.crews - int(absences[day]))
        jobs.sort(key=lambda j: (j["kind"] != "corrective", j["created"]))
        for j in list(jobs):
            needs_part = j["kind"] in ("corrective", "planned")
            if crews == 0:
                m["crew_shortage_job_days"] += 1
                continue
            if needs_part and stock == 0:
                m["part_shortage_job_days"] += 1
                continue
            crews -= 1
            stock -= needs_part
            jobs.remove(j)
            e = eng[j["slot"]]
            if day - j["created"] > 2:
                m["delayed_jobs"] += 1
            dur = {"corrective": p.corrective_days, "planned": p.planned_days, "inspection": p.inspection_days}[j["kind"]]
            e["maint_until"] = day + dur
            if needs_part:  # install next engine from the shared replacement queue
                if j["kind"] == "planned":
                    m["planned_replacements"] += 1
                    m["wasted_life_cycles"] += lengths[e["unit"]] - e["cycle"]
                e["k"] += 1
                e["unit"], e["cycle"] = queue[e["slot"]][e["k"] % len(queue[e["slot"]])]
                e.update(failed=False, held=False, rec_day=None, queued=None)
            else:
                m["inspections"] += 1
                e["queued"] = None

        # 2. fly available aircraft; accrue degradation; detect failures
        for a in range(p.n_aircraft):
            idx = range(a * p.engines_per_aircraft, (a + 1) * p.engines_per_aircraft)
            ok = all(day >= eng[i]["maint_until"] and not eng[i]["failed"] and not eng[i]["held"] for i in idx)
            availability.append((day, a, ok))
            if not ok:
                continue
            for i in idx:
                e = eng[i]
                e["cycle"] += p.cycles_per_day
                if e["cycle"] >= lengths[e["unit"]]:
                    e["cycle"] = lengths[e["unit"]]
                    e["failed"] = True
                    m["failures"] += 1
                    jobs = [j for j in jobs if j["slot"] != i]
                    jobs.append({"slot": i, "kind": "corrective", "created": day})
                    e["queued"] = "corrective"

        # 3. predictive policy: daily prediction + TrustTwin gate + human review
        if policy == "predictive":
            for i, e in enumerate(eng):
                if e["failed"] or day < e["maint_until"] or e["queued"] in ("corrective", "inspection"):
                    continue
                if dropouts[day, i]:
                    m["degraded_predictions"] += 1
                    if not e["queued"]:
                        jobs.append({"slot": i, "kind": "inspection", "created": day})
                        e["queued"] = "inspection"
                    continue
                row = table[e["unit"]].iloc[min(e["cycle"], lengths[e["unit"]]) - 1]
                if row["lo"] <= p.hold_lower_bound:
                    e["held"] = True    # conservative hold while awaiting planned replacement
                if e["queued"] == "planned":
                    continue
                if row["lo"] <= p.trigger_lower_bound and e["rec_day"] is None:
                    e["rec_day"] = day
                    m["recommendations"] += 1
                if e["rec_day"] is not None and day - e["rec_day"] >= p.review_delay_days:
                    jobs.append({"slot": i, "kind": "planned", "created": day})
                    e["queued"] = "planned"

    m["unresolved_at_end"] = len(jobs)
    av = pd.DataFrame(availability, columns=["day", "aircraft", "ok"])
    daily = av.groupby("day")["ok"].mean()
    down_days = int((~av["ok"]).sum())
    return {"policy": policy, "metrics": {**m, "availability_pct": round(100 * float(av["ok"].mean()), 2),
                                          "aircraft_down_days": down_days, "downtime_hours": down_days * 24},
            "daily_availability_pct": [round(100 * float(v), 1) for v in daily.to_numpy()]}


def compare(p: SimParams) -> dict:
    reactive = run_policy("reactive", p)
    predictive = run_policy("predictive", p)
    rm, pm = reactive["metrics"], predictive["metrics"]
    result = {
        "label": LABEL, "params": p.__dict__,
        "identical_conditions": "Same seed, initial fleet, engine replacement sequence, dropouts, absences and deliveries.",
        "reactive": reactive, "predictive": predictive,
        "delta": {k: round(pm[k] - rm[k], 2) for k in rm},
        "data_note": "Engine degradation replays C-MAPSS FD001 hold-out run-to-failure trajectories; "
                     "predictions come from the trained model. Fleet, crews and parts are synthetic.",
    }
    result["result_hash"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
