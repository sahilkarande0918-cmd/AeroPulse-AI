"""TrustTwin gating (6-8), planner constraints (9-11), simulator determinism/fairness (14-15)."""
import copy
import random
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from app.config import DEFAULT_TRUST_THRESHOLDS as TH
from app.services import planner, simulator, trust
from app.services.planner import PartStock, Problem, Task, Tech
from ml.inference import ARTIFACT_DIR, load_model

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def rows():
    raw = pd.read_csv(ARTIFACT_DIR / "holdout_trajectories.csv.gz")
    g = raw[raw.unit == sorted(raw.unit.unique())[0]].head(120)
    return [{"cycle": int(r["cycle"]), "recorded_at": NOW - timedelta(hours=12 * (120 - i)),
             "values": {f"s{k}": float(r[f"s{k}"]) for k in range(1, 22)}} for i, r in enumerate(g.to_dict("records"), 1)]


def _assess(rows, now=NOW):
    return trust.assess(rows, now, load_model(), TH)


def test_clean_input_is_valid(rows):
    a = _assess(rows)
    assert a["state"] == "VALID" and a["rul"] is not None and a["rul_lower"] <= a["rul"] <= a["rul_upper"]
    assert a["evidence"] and all("contribution" in e for e in a["evidence"])


def test_missing_sensor_detected(rows):  # scenario 6
    r = copy.deepcopy(rows)
    del r[-1]["values"]["s11"]
    a = _assess(r)
    assert a["state"] == "DEGRADED" and "s11" in a["imputed"]
    assert any(c["id"] == "missing" and c["status"] == "warn" for c in a["checks"])
    for s in ("s2", "s3", "s4"):
        del r[-1]["values"][s]
    a = _assess(r)
    assert a["state"] == "UNAVAILABLE" and a["rul"] is None


def test_stale_data_detected(rows):  # scenario 7
    assert _assess(rows, NOW + timedelta(hours=72))["state"] == "DEGRADED"
    a = _assess(rows, NOW + timedelta(days=30))
    assert a["state"] == "UNAVAILABLE" and a["rul"] is None
    assert any(c["id"] == "stale" and c["status"] == "fail" for c in a["checks"])


@pytest.mark.parametrize("bad", [float("nan"), "abc", 1e9, None])
def test_invalid_input_never_trusted(rows, bad):  # scenario 8
    r = copy.deepcopy(rows)
    r[-1]["values"]["s3"] = bad
    a = _assess(r)
    assert a["state"] != "VALID"
    if bad == 1e9 or bad == "abc":
        assert a["state"] == "UNAVAILABLE" and a["rul"] is None


def test_unit_mismatch_flagged(rows):
    r = copy.deepcopy(rows)
    r[-1]["values"]["s4"] /= 1.8   # Kelvin instead of Rankine
    a = _assess(r)
    assert a["state"] == "UNAVAILABLE" and any(c["id"] == "units" and c["status"] == "fail" for c in a["checks"])


def test_spike_and_short_history(rows):
    r = copy.deepcopy(rows)
    r[-1]["values"]["s7"] += 40 * load_model().sensor_stats["s7"]["step_std"]
    assert _assess(r)["state"] in ("DEGRADED", "UNAVAILABLE")
    assert _assess(rows[:8], rows[7]["recorded_at"])["state"] == "DEGRADED"
    assert _assess(rows[:3], rows[2]["recorded_at"])["state"] == "UNAVAILABLE"
    assert _assess([])["state"] == "UNAVAILABLE"


# ------------------------------------------------------------------ planner
def shifts(h):
    return [(d * 24 + 16, d * 24 + 32) for d in range(h // 24 + 1)]


def base_problem():
    techs = [Tech("T1", ["powerplant", "ndt"], shifts(168)), Tech("T2", ["powerplant"], shifts(168)), Tech("T3", ["avionics"], shifts(168))]
    tasks = [Task("A", "AC1", "ndt", 4, 1, 30, release=2), Task("B", "AC1", "powerplant", 6, 1, 60, parts={"KIT": 1}, predecessors=["A"]),
             Task("C", "AC2", "powerplant", 6, 2, 50, parts={"KIT": 1}), Task("D", "AC3", "avionics", 3, 3, 100)]
    return Problem(168, tasks, techs, {"KIT": PartStock(2, [])})


@pytest.mark.parametrize("solve", [planner.solve_cpsat, planner.solve_greedy])
def test_part_unavailability_changes_plan(solve):  # scenario 9
    ok = solve(base_problem())
    assert ok["kpis"]["unscheduled"] == 0
    p = base_problem()
    p.parts["KIT"] = PartStock(0, [(80, 1)])
    r = solve(p)
    starts = {a["task"]: a["start"] for a in r["assignments"]}
    assert r["kpis"]["unscheduled"] == 1                     # only one kit ever arrives
    assert all(starts[t] >= 80 for t in starts if t in ("B", "C"))
    p.parts["KIT"] = PartStock(0, [])
    r = solve(p)
    reasons = {u["task"]: u["reason"] for u in r["unscheduled"]}
    assert set(reasons) == {"B", "C"} and "KIT" in reasons["B"]


@pytest.mark.parametrize("solve", [planner.solve_cpsat, planner.solve_greedy])
def test_technician_shortage_affects_schedule(solve):  # scenario 10
    base = solve(base_problem())
    p = base_problem()
    p.techs = [t for t in p.techs if t.id != "T2"]
    p.techs[0].blocked = planner.merge(p.techs[0].blocked + [(0, 40)])
    r = solve(p)
    assert r["kpis"]["makespan_h"] > base["kpis"]["makespan_h"]
    assert all(a["technician"] != "T2" for a in r["assignments"])
    p.techs = [t for t in p.techs if t.id != "T3"]
    r = solve(p)
    assert any(u["task"] == "D" and "avionics" in u["reason"] for u in r["unscheduled"])


def _random_problem(seed):
    rng = random.Random(seed)
    skills = ["powerplant", "ndt", "avionics"]
    techs = [Tech(f"T{i}", rng.sample(skills, rng.randint(1, 2)),
                  planner.merge(shifts(120) + ([(rng.randint(0, 60), rng.randint(61, 100))] if rng.random() < 0.5 else [])))
             for i in range(rng.randint(1, 4))]
    tasks = []
    for i in range(rng.randint(0, 9)):
        preds = [f"W{rng.randint(0, i - 1)}"] if i and rng.random() < 0.3 else []
        tasks.append(Task(f"W{i}", f"AC{rng.randint(1, 3)}", rng.choice(skills), rng.randint(1, 8), rng.randint(1, 4),
                          rng.randint(0, 120), release=rng.choice([0, 0, 4]), predecessors=preds,
                          parts={"P1": rng.randint(1, 2)} if rng.random() < 0.4 else {}))
    return Problem(120, tasks, techs, {"P1": PartStock(rng.randint(0, 3), [(rng.randint(10, 100), rng.randint(0, 2))])})


@pytest.mark.parametrize("seed", range(25))
def test_optimiser_enforces_hard_constraints(seed):  # scenario 11 (random instances, independent verifier)
    p = _random_problem(seed)
    for solve in (planner.solve_cpsat, planner.solve_greedy):
        r = solve(p)
        assert r["violations"] == [] and planner.verify(p, r) == []
        assert len(r["assignments"]) + len(r["unscheduled"]) == len(p.tasks)
    assert planner.solve_cpsat(p)["objective"] <= planner.solve_greedy(p)["objective"] + 1e-6


def test_empty_queue_and_precedence():
    empty = Problem(48, [], [Tech("T1", ["ndt"], [])], {})
    assert planner.solve_cpsat(empty)["kpis"]["scheduled"] == 0
    p = base_problem()
    r = planner.solve_cpsat(p)
    s = {a["task"]: a for a in r["assignments"]}
    assert s["B"]["start"] >= s["A"]["end"]
    p.tasks[0].skill = "hydraulics"  # A impossible -> B blocked by predecessor
    r = planner.solve_cpsat(p)
    reasons = {u["task"]: u["reason"] for u in r["unscheduled"]}
    assert "hydraulics" in reasons["A"] and "predecessor" in reasons["B"]


def test_verifier_catches_violations():
    p = base_problem()
    r = planner.solve_cpsat(p)
    bad = copy.deepcopy(r)
    bad["assignments"][0]["technician"] = "T3"   # wrong skill
    assert planner.verify(p, bad)


# ------------------------------------------------------------------ simulator
def test_simulation_repeatable_with_seed():  # scenario 14
    a, b = simulator.compare(simulator.SimParams(seed=11, days=60)), simulator.compare(simulator.SimParams(seed=11, days=60))
    assert a["result_hash"] == b["result_hash"] and a["reactive"] == b["reactive"]
    assert simulator.compare(simulator.SimParams(seed=12, days=60))["result_hash"] != a["result_hash"]


def test_policies_share_identical_conditions(monkeypatch):  # scenario 15
    seen = []
    orig = simulator._events

    def spy(*args):
        out = orig(*args)
        seen.append(repr(out))
        return out
    monkeypatch.setattr(simulator, "_events", spy)
    r = simulator.compare(simulator.SimParams(seed=3, days=60))
    assert len(seen) == 2 and seen[0] == seen[1]
    assert r["reactive"]["metrics"]["recommendations"] == 0 and "simulated" in r["label"]
