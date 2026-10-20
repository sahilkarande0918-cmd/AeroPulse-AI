"""Glue between persistence, TrustTwin assessment, recommendations and the planner."""
from collections.abc import Collection, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import DEFAULT_TRUST_THRESHOLDS
from app.database import utcnow
from app.models import AppSetting, Engine, Part, Prediction, Recommendation, SensorReading, Technician, WorkOrder
from app.services import planner, trust
from ml.inference import load_model

SHIFT_TZ = ZoneInfo("Asia/Kolkata")   # technician shift hours are local base time
APPROVAL_LEAD_HOURS = 4               # pending work orders cannot start before review
HORIZON_HOURS = 14 * 24
HOURS_PER_CYCLE = 12                  # synthetic utilisation used to timestamp replayed cycles

# Prototype action catalogue (fictional part numbers; real procedures must come from approved manuals).
ACTIONS: dict[str, dict[str, Any]] = {
    "replace": {"action": "Plan engine hot-section module replacement", "task_type": "replacement",
                "skill": "powerplant", "duration": 8, "parts": [{"part_number": "APX-HPT-MOD-KIT", "qty": 1}]},
    "inspect": {"action": "Borescope inspection of HPC/HPT stages", "task_type": "inspection",
                "skill": "ndt", "duration": 4, "parts": [{"part_number": "APX-BORESCOPE-SEAL", "qty": 1}]},
    "verify": {"action": "Verify sensors / data link and re-collect readings", "task_type": "troubleshooting",
               "skill": "avionics", "duration": 3, "parts": []},
}


def thresholds(db: Session) -> dict:
    row = db.get(AppSetting, "trust_thresholds")
    return {**DEFAULT_TRUST_THRESHOLDS, **(row.value if row else {})}


def readings_for(db: Session, engine_id: int) -> list[dict]:
    rows = db.scalars(select(SensorReading).where(SensorReading.engine_id == engine_id)
                      .order_by(SensorReading.cycle)).all()
    return [{"cycle": r.cycle, "recorded_at": r.recorded_at, "values": r.values} for r in rows]


def save_prediction(db: Session, engine: Engine, a: dict, scenario_run_id: int | None = None) -> Prediction:
    p = Prediction(engine_id=engine.id, cycle=a.get("cycle") or 0, model_version=a["model_version"],
                   state=a["state"], rul=a["rul"], rul_lower=a["rul_lower"], rul_upper=a["rul_upper"],
                   quality={k: a.get(k) for k in ("checks", "summary", "reasons", "imputed", "n_cycles",
                                                  "data_age_hours", "last_recorded_at")},
                   evidence=a["evidence"], scenario_run_id=scenario_run_id)
    db.add(p)
    db.flush()
    return p


def recommend(a: dict, th: dict) -> dict | None:
    """Rule-based advisory recommendation from a gated prediction. Thresholds are prototype settings."""
    state, lo = a["state"], a["rul_lower"]
    days_left = (lo or 0) / th["cycles_per_day"]
    if state == "UNAVAILABLE":
        spec, prio = ACTIONS["verify"], 2
        why = "Prediction withheld by TrustTwin. " + " ".join(a.get("reasons", [])[:2])
        due_days = 2
    elif state == "DEGRADED":
        spec, prio = ACTIONS["verify"], 2
        why = "Inputs degraded; verify before relying on the estimate. " + " ".join(a.get("reasons", [])[:2])
        due_days = 2
        if lo is not None and lo <= th["rul_warning_lower_bound"]:
            spec, prio = ACTIONS["inspect"], 1
            why += f" Estimate (lower bound {lo:.0f} cycles) also near warning level: inspect physically."
    elif lo is not None and lo <= th["rul_critical_lower_bound"]:
        spec, prio, due_days = ACTIONS["replace"], 1, max(days_left, 0.5)
        why = (f"Predicted RUL {a['rul']:.0f} cycles, 90% interval [{lo:.0f}, {a['rul_upper']:.0f}]. "
               f"Lower bound at or below {th['rul_critical_lower_bound']} cycles.")
    elif lo is not None and lo <= th["rul_warning_lower_bound"]:
        spec, prio, due_days = ACTIONS["inspect"], 2, max(days_left, 1)
        why = (f"Predicted RUL {a['rul']:.0f} cycles, 90% interval [{lo:.0f}, {a['rul_upper']:.0f}]. "
               f"Lower bound at or below {th['rul_warning_lower_bound']} cycles.")
    else:
        return None
    return {**spec, "priority": prio, "rationale": why.strip(), "due_days": round(due_days, 2)}


def refresh_engine(db: Session, engine: Engine, now: datetime | None = None) -> Prediction:
    """Assess an engine, persist the prediction and (if actionable and none open) a recommendation."""
    now = now or utcnow()
    th = thresholds(db)
    a = trust.assess(readings_for(db, engine.id), now, load_model(), th)
    pred = save_prediction(db, engine, a)
    rec = recommend(a, th)
    open_rec = db.scalar(select(Recommendation).where(
        Recommendation.engine_id == engine.id, Recommendation.status == "proposed",
        Recommendation.scenario_run_id.is_(None)))
    if rec and not open_rec:
        db.add(Recommendation(prediction_id=pred.id, aircraft_id=engine.aircraft_id, engine_id=engine.id,
                              action=rec["action"], priority=rec["priority"], rationale=rec["rationale"]))
    return pred


def latest_predictions(db: Session) -> dict[int, Prediction]:
    sub = (select(Prediction.engine_id, func.max(Prediction.id).label("mid"))
           .where(Prediction.scenario_run_id.is_(None)).group_by(Prediction.engine_id).subquery())
    rows = db.scalars(select(Prediction).join(sub, Prediction.id == sub.c.mid)).all()
    return {p.engine_id: p for p in rows}


def next_wo_code(db: Session) -> str:
    n = db.scalar(select(func.count(WorkOrder.id))) or 0
    return f"WO-{n + 1001:04d}"


def work_order_from_recommendation(db: Session, rec: Recommendation, spec: dict, now: datetime) -> WorkOrder:
    wo = WorkOrder(code=next_wo_code(db), aircraft_id=rec.aircraft_id, engine_id=rec.engine_id,
                   title=spec["action"], task_type=spec["task_type"], required_skill=spec["skill"],
                   duration_hours=spec["duration"], priority=rec.priority,
                   due_at=now + timedelta(days=spec.get("due_days", 3)), approval_state="approved",
                   parts=spec["parts"], source="recommendation", external_id=f"REC-{rec.id}")
    db.add(wo)
    db.flush()
    return wo


# ---------------------------------------------------------------------------- planning problem
def _hour(dt: datetime, t0: datetime) -> int:
    return int((dt - t0).total_seconds() // 3600)


def horizon_start(now: datetime | None = None) -> datetime:
    return (now or utcnow()).replace(minute=0, second=0, microsecond=0)


def tech_blocked(t: Technician, t0: datetime, horizon: int) -> list[tuple[int, int]]:
    if not t.available:
        return [(0, horizon)]
    blocked = []
    local0 = t0.astimezone(SHIFT_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    for d in range(-1, horizon // 24 + 2):
        day = local0 + timedelta(days=d)
        s, e = day.replace(hour=t.shift_start_hour), day.replace(hour=t.shift_end_hour)
        nxt = (day + timedelta(days=1)).replace(hour=t.shift_start_hour)
        blocked.append((_hour(e.astimezone(UTC), t0), _hour(nxt.astimezone(UTC), t0)))
        if d == -1:
            blocked.append((-48, _hour(s.astimezone(UTC), t0)))
    for u in t.unavailable or []:
        blocked.append((_hour(datetime.fromisoformat(u["start"]), t0), _hour(datetime.fromisoformat(u["end"]), t0)))
    return sorted((max(0, a), min(horizon, b)) for a, b in blocked if b > 0 and a < horizon and b > a)


def build_problem(db: Session, now: datetime | None = None, *, extra_tasks: Sequence[dict] = (),
                  unavailable_techs: Collection[str] = frozenset(), part_overrides: dict | None = None,
                  weights: dict | None = None) -> tuple[planner.Problem, datetime, dict]:
    t0 = horizon_start(now)
    H = HORIZON_HOURS
    wos = db.scalars(select(WorkOrder).where(WorkOrder.status.in_(["open", "scheduled"]),
                                             WorkOrder.approval_state != "rejected")
                     .order_by(WorkOrder.code)).all()
    meta = {}
    tasks = []
    for w in wos:
        tasks.append(planner.Task(
            id=w.code, aircraft=w.aircraft.tail, skill=w.required_skill, duration=w.duration_hours,
            priority=w.priority, due=_hour(w.due_at, t0),
            release=APPROVAL_LEAD_HOURS if w.approval_state == "pending" else 0,
            parts={p["part_number"]: int(p["qty"]) for p in w.parts}, predecessors=list(w.predecessor_codes),
            title=w.title))
        meta[w.code] = {"approval_state": w.approval_state, "engine_id": w.engine_id, "source": w.source}
    for x in extra_tasks:
        tasks.append(planner.Task(**{k: v for k, v in x.items() if k in planner.Task.__dataclass_fields__}))
        meta[x["id"]] = {"approval_state": "proposed", "engine_id": x.get("engine_id"), "source": "trusttwin"}
    techs = [planner.Tech(t.code, list(t.skills), [(0, H)] if t.code in unavailable_techs else tech_blocked(t, t0, H))
             for t in db.scalars(select(Technician).order_by(Technician.code))]
    stocks = {}
    for p in db.scalars(select(Part)):
        over = (part_overrides or {}).get(p.part_number, {})
        on_hand = over.get("on_hand", p.on_hand)
        eta = over.get("eta", p.replenishment_eta)
        arrivals = [(max(0, _hour(eta, t0)), p.replenishment_qty)] if eta and p.replenishment_qty and _hour(eta, t0) < H else []
        stocks[p.part_number] = planner.PartStock(on_hand, arrivals)
    for t in tasks:  # unknown part numbers become zero-stock so the planner reports them, never ignores them
        for pn in t.parts:
            stocks.setdefault(pn, planner.PartStock(0, []))
    return planner.Problem(H, tasks, techs, stocks, weights or {}), t0, meta


