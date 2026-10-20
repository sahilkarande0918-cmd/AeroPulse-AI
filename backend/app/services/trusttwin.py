"""TrustTwin what-if scenarios: perturb data/resources, re-assess, re-plan, compare, explain.

Scenarios are sandboxed: they never modify live work orders, inventory or rosters.
"""
import copy
import hashlib
import json
from datetime import timedelta
from functools import lru_cache

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import utcnow
from app.models import Aircraft, Engine, Recommendation, ScenarioRun, Schedule
from app.services import fleet, planner, trust
from ml.inference import ARTIFACT_DIR, load_model


class ScenarioParams(BaseModel):
    engine_id: int
    seed: int = 7
    advance_cycles: int = Field(0, ge=0, le=200, description="Replay further real degradation (developing fault)")
    dropout_sensors: list[str] = Field(default_factory=list, description="Sensors missing from latest readings")
    dropout_last_n: int = Field(1, ge=1, le=50)
    bias_sensor: str | None = None
    bias_sigma: float = Field(0, ge=0, le=100, description="Step bias on bias_sensor, in typical step std")
    noise_sigma: float = Field(0, ge=0, le=20, description="Seeded Gaussian noise added to latest 10 readings")
    stale_hours: float = Field(0, ge=0, le=2000)
    unavailable_parts: list[str] = Field(default_factory=list)
    part_delay_days: int = Field(0, ge=0, le=60)
    unavailable_technicians: list[str] = Field(default_factory=list)
    extra_inspection_aircraft: list[int] = Field(default_factory=list, description="Aircraft needing simultaneous inspections")


@lru_cache(maxsize=1)
def holdout_raw() -> pd.DataFrame:
    return pd.read_csv(ARTIFACT_DIR / "holdout_trajectories.csv.gz")


def _future_readings(engine: Engine, after_cycle: int, n: int) -> list[dict]:
    if not n or engine.source_unit is None:
        return []
    raw = holdout_raw()
    g = raw[(raw.unit == engine.source_unit) & (raw.cycle > after_cycle)].head(n)
    return [{"cycle": int(r["cycle"]), "values": {k: float(v) for k, v in r.items() if k.startswith("s")}}
            for r in g.to_dict("records")]


def perturb(readings: list[dict], engine: Engine, p: ScenarioParams, now) -> tuple[list[dict], object, list[str]]:
    rs = copy.deepcopy(readings)
    notes = []
    last_cycle = rs[-1]["cycle"] if rs else 0
    fut = _future_readings(engine, last_cycle, p.advance_cycles)
    for k, r in enumerate(fut):
        r["recorded_at"] = now - timedelta(hours=fleet.HOURS_PER_CYCLE * (len(fut) - 1 - k))
    if fut:
        notes.append(f"Replayed {len(fut)} further recorded cycles of degradation (to cycle {fut[-1]['cycle']}).")
    elif p.advance_cycles:
        notes.append("No further recorded cycles available for this engine (end of trajectory).")
    rs += fut
    rng = np.random.default_rng(p.seed)
    model = load_model()
    if p.noise_sigma and rs:
        for r in rs[-10:]:
            for s in model.sensors:
                if r["values"].get(s) is not None:
                    r["values"][s] = float(r["values"][s]) + rng.normal(0, p.noise_sigma * model.sensor_stats[s]["step_std"])
        notes.append(f"Added seeded noise ({p.noise_sigma} x step std) to the latest 10 readings.")
    if p.bias_sensor and p.bias_sigma and rs:
        s = p.bias_sensor
        rs[-1]["values"][s] = float(rs[-1]["values"][s]) + p.bias_sigma * model.sensor_stats[s]["step_std"]
        notes.append(f"Injected a {p.bias_sigma:g}-sigma step on {s} in the latest reading.")
    for r in rs[-p.dropout_last_n:] if p.dropout_sensors else []:
        for s in p.dropout_sensors:
            r["values"].pop(s, None)
    if p.dropout_sensors:
        notes.append(f"Sensor dropout: {', '.join(p.dropout_sensors)} missing in last {p.dropout_last_n} reading(s).")
    eval_now = now
    if p.stale_hours:
        eval_now = max(now, rs[-1]["recorded_at"]) + timedelta(hours=p.stale_hours)
        notes.append(f"Evaluated {p.stale_hours:g} h after the last reading (stale data link).")
    return rs, eval_now, notes


def _rec_task(engine: Engine, a: dict, th: dict, tag: str) -> dict | None:
    rec = fleet.recommend(a, th)
    if not rec:
        return None
    return {"id": f"{tag}-E{engine.id}", "aircraft": engine.aircraft.tail, "skill": rec["skill"],
            "duration": rec["duration"], "priority": rec["priority"], "due": int(rec["due_days"] * 24),
            "release": fleet.APPROVAL_LEAD_HOURS, "parts": {x["part_number"]: x["qty"] for x in rec["parts"]},
            "title": rec["action"], "engine_id": engine.id, "_rec": rec}


def _outcomes(plan: dict, assessments: dict[int, dict], task_engine: dict[str, int], th: dict) -> dict:
    """Projected consequences: risk margin of each assessed engine vs when its maintenance starts."""
    risk = []
    starts = {a["task"]: a["start"] for a in plan["assignments"]}
    for task, eid in task_engine.items():
        a = assessments.get(eid)
        if not a or a["rul_lower"] is None:
            continue
        start = starts.get(task)
        cycles_until = None if start is None else start / 24 * th["cycles_per_day"]
        margin = None if cycles_until is None else a["rul_lower"] - cycles_until
        risk.append({"task": task, "engine_id": eid, "rul_lower": round(a["rul_lower"], 1),
                     "starts_in_h": start, "cycles_flown_before_start": None if cycles_until is None else round(cycles_until, 1),
                     "margin_cycles": None if margin is None else round(margin, 1),
                     "flag": "unscheduled" if start is None else ("margin exhausted" if margin < 0 else "ok")})
    down = {}
    for a in plan["assignments"]:
        down[a["aircraft"]] = down.get(a["aircraft"], 0) + (a["end"] - a["start"])
    return {"engine_risk": risk, "aircraft_maintenance_hours": down,
            "note": "Planning projection only; not a dispatch or airworthiness determination."}


def _diff(base: dict, rev: dict) -> list[dict]:
    b = {a["task"]: a for a in base["assignments"]}
    r = {a["task"]: a for a in rev["assignments"]}
    ru = {u["task"]: u["reason"] for u in rev["unscheduled"]}
    out = []
    for t in sorted(set(b) | set(r) | set(ru)):
        if t in b and t in r:
            if b[t]["start"] != r[t]["start"] or b[t]["technician"] != r[t]["technician"]:
                out.append({"task": t, "change": "moved", "from": b[t]["start"], "to": r[t]["start"],
                            "tech_from": b[t]["technician"], "tech_to": r[t]["technician"]})
        elif t in b and t in ru:
            out.append({"task": t, "change": "now unscheduled", "reason": ru[t]})
        elif t in r and t not in b:
            out.append({"task": t, "change": "added", "to": r[t]["start"], "tech_to": r[t]["technician"]})
    return out


def run(db: Session, p: ScenarioParams, user_id: int | None, now=None) -> ScenarioRun:
    engine = db.get(Engine, p.engine_id)
    if engine is None:
        raise LookupError("engine not found")
    model = load_model()
    th = fleet.thresholds(db)
    now = now or utcnow()
    readings = fleet.readings_for(db, engine.id)
    base_a = trust.assess(readings, now, model, th)
    pert, eval_now, notes = perturb(readings, engine, p, now)
    rev_a = trust.assess(pert, eval_now, model, th)

    base_task = _rec_task(engine, base_a, th, "BASE")
    rev_task = _rec_task(engine, rev_a, th, "REV")
    extra = []
    for ac_id in p.extra_inspection_aircraft:
        ac = db.get(Aircraft, ac_id)
        if ac and ac.id != engine.aircraft_id:
            spec = fleet.ACTIONS["inspect"]
            extra.append({"id": f"INSP-{ac.tail}", "aircraft": ac.tail, "skill": spec["skill"], "duration": spec["duration"],
                          "priority": 2, "due": 48, "release": fleet.APPROVAL_LEAD_HOURS,
                          "parts": {x["part_number"]: x["qty"] for x in spec["parts"]}, "title": spec["action"]})
    if extra:
        notes.append(f"{len(extra)} additional aircraft require inspections in the same window.")
    t0 = fleet.horizon_start(now)
    overrides = {pn: {"on_hand": 0, **({"eta": t0 + timedelta(days=p.part_delay_days + 14)} if p.part_delay_days else {})}
                 for pn in p.unavailable_parts}
    if p.unavailable_parts:
        notes.append(f"Spare parts unavailable: {', '.join(p.unavailable_parts)}"
                     + (f" (replenishment slips {p.part_delay_days} days)." if p.part_delay_days else "."))
    if p.unavailable_technicians:
        notes.append(f"Technicians unavailable: {', '.join(p.unavailable_technicians)}.")

    base_prob, _, meta = fleet.build_problem(db, now, extra_tasks=[base_task] if base_task else [])
    rev_prob, _, rev_meta = fleet.build_problem(
        db, now, extra_tasks=([rev_task] if rev_task else []) + extra,
        unavailable_techs=set(p.unavailable_technicians), part_overrides=overrides)
    base_plan = planner.solve_cpsat(base_prob)
    rev_plan = planner.solve_cpsat(rev_prob)
    rev_greedy = planner.solve_greedy(rev_prob)

    task_engine = {k: v["engine_id"] for k, v in {**meta, **rev_meta}.items() if v.get("engine_id")}
    assessments = {e: base_a for e in task_engine.values()}
    assessments[engine.id] = base_a
    base_out = _outcomes(base_plan, assessments, task_engine, th)
    assessments[engine.id] = rev_a
    rev_out = _outcomes(rev_plan, assessments, task_engine, th)
    diff = _diff(base_plan, rev_plan)

    explain = list(notes)
    if base_a["state"] != rev_a["state"]:
        explain.append(f"TrustTwin state {base_a['state']} -> {rev_a['state']}: " + "; ".join(rev_a.get("reasons", [])[:3]))
    if base_a["rul"] is not None and rev_a["rul"] is not None and abs(base_a["rul"] - rev_a["rul"]) >= 1:
        explain.append(f"Predicted RUL {base_a['rul']:.0f} -> {rev_a['rul']:.0f} cycles "
                       f"(lower bound {base_a['rul_lower']:.0f} -> {rev_a['rul_lower']:.0f}).")
    if rev_a["state"] == "UNAVAILABLE":
        explain.append("No RUL estimate was manufactured; the recommended response is verification.")
    if (base_task or {}).get("title") != (rev_task or {}).get("title"):
        explain.append(f"Recommended action: '{(base_task or {}).get('title', 'none')}' -> '{(rev_task or {}).get('title', 'none')}'.")
    for d in diff:
        if d["change"] == "moved":
            explain.append(f"{d['task']} moved +{d['from']} h -> +{d['to']} h ({d['tech_from']} -> {d['tech_to']}).")
        elif d["change"] == "now unscheduled":
            explain.append(f"{d['task']} can no longer be scheduled: {d['reason']}")
    for u in rev_plan["unscheduled"]:
        if u["task"].startswith(("REV", "INSP")):
            explain.append(f"{u['task']} not schedulable: {u['reason']}")
    kb, kr = base_plan["kpis"], rev_plan["kpis"]
    explain.append(f"Plan KPIs: late tasks {kb['late_tasks']} -> {kr['late_tasks']}, unscheduled "
                   f"{kb['unscheduled']} -> {kr['unscheduled']}, objective {base_plan['objective']:.0f} -> {rev_plan['objective']:.0f} "
                   f"(rule-based baseline on revised inputs: {rev_greedy['objective']:.0f}).")

    def pub(a):
        return {k: a.get(k) for k in ("state", "summary", "reasons", "checks", "rul", "rul_lower", "rul_upper",
                                      "evidence", "imputed", "cycle", "n_cycles", "data_age_hours", "model_version")}

    result = {
        "engine": {"id": engine.id, "serial": engine.serial, "aircraft": engine.aircraft.tail,
                   "source": f"{engine.source_dataset} unit {engine.source_unit}"},
        "baseline": {"assessment": pub(base_a), "recommendation": base_task and base_task["_rec"],
                     "plan": base_plan, "outcomes": base_out},
        "revised": {"assessment": pub(rev_a), "recommendation": rev_task and rev_task["_rec"],
                    "plan": rev_plan, "outcomes": rev_out, "rule_based_plan_kpis": rev_greedy["kpis"],
                    "rule_based_objective": rev_greedy["objective"]},
        "diff": diff, "explanation": explain, "horizon_start": t0.isoformat(),
        "sandbox_note": "What-if scenario: live work orders, inventory and rosters are unchanged.",
    }
    det = {k: result[k] for k in ("baseline", "revised", "diff")}
    run_ = ScenarioRun(kind="trusttwin", user_id=user_id, seed=p.seed, params=p.model_dump(), result=result,
                       result_hash=hashlib.sha256(json.dumps(det, sort_keys=True, default=str).encode()).hexdigest())
    db.add(run_)
    db.flush()
    pred = fleet.save_prediction(db, engine, rev_a, scenario_run_id=run_.id)
    if rev_task:
        r = rev_task["_rec"]
        db.add(Recommendation(prediction_id=pred.id, aircraft_id=engine.aircraft_id, engine_id=engine.id,
                              action=r["action"], priority=r["priority"], rationale=r["rationale"],
                              scenario_run_id=run_.id))
    for plan, prob, label in ((base_plan, base_prob, "baseline"), (rev_plan, rev_prob, "revised")):
        db.add(Schedule(created_by=user_id, solver=f"cp-sat ({label})", horizon_start=t0,
                        input_hash=fleet.problem_hash(prob), result=plan, scenario_run_id=run_.id))
    db.flush()
    return run_
