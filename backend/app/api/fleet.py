from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import iso
from app.api.maintenance import wo_out
from app.api.parts import parts_view
from app.database import get_db
from app.models import (
    Aircraft,
    AuditEvent,
    Engine,
    MaintenanceRecord,
    Prediction,
    Recommendation,
    ScenarioRun,
    SensorReading,
    User,
    WorkOrder,
)
from app.security import audit, require
from app.services import fleet
from ml.inference import load_model

router = APIRouter(tags=["fleet"])
OPEN = ("open", "scheduled", "in_progress")


def pred_out(p: Prediction | None, full: bool = False) -> dict | None:
    if p is None:
        return None
    out = {"id": p.id, "engine_id": p.engine_id, "created_at": iso(p.created_at), "cycle": p.cycle,
           "model_version": p.model_version, "state": p.state, "rul": p.rul, "rul_lower": p.rul_lower,
           "rul_upper": p.rul_upper, "summary": p.quality.get("summary"), "reasons": p.quality.get("reasons", []),
           "last_recorded_at": p.quality.get("last_recorded_at"), "data_age_hours": p.quality.get("data_age_hours")}
    if full:
        out.update(checks=p.quality.get("checks", []), evidence=p.evidence, imputed=p.quality.get("imputed", {}),
                   n_cycles=p.quality.get("n_cycles"), scenario_run_id=p.scenario_run_id)
    return out


def maintenance_state(preds: list[Prediction | None], wos: list[WorkOrder], th: dict) -> str:
    if any(w.status == "in_progress" for w in wos):
        return "in_maintenance"
    lows = [p.rul_lower for p in preds if p and p.rul_lower is not None]
    if any(lo <= th["rul_critical_lower_bound"] for lo in lows) or any(w.priority == 1 for w in wos):
        return "action_required"
    if any(p is None or p.state != "VALID" for p in preds) or any(lo <= th["rul_warning_lower_bound"] for lo in lows):
        return "watch"
    return "routine"


def _fleet_rows(db: Session) -> list[dict]:
    th = fleet.thresholds(db)
    latest = fleet.latest_predictions(db)
    open_wos = db.scalars(select(WorkOrder).where(WorkOrder.status.in_(OPEN), WorkOrder.approval_state != "rejected")).all()
    rows = []
    for ac in db.scalars(select(Aircraft).order_by(Aircraft.tail)):
        wos = [w for w in open_wos if w.aircraft_id == ac.id]
        preds = [latest.get(e.id) for e in ac.engines]
        last = max((p.quality.get("last_recorded_at") for p in preds if p and p.quality.get("last_recorded_at")), default=None)
        rows.append({"id": ac.id, "tail": ac.tail, "type_name": ac.type_name, "base": ac.base,
                     "maintenance_state": maintenance_state(preds, wos, th), "last_data_update": last,
                     "open_work_orders": len(wos),
                     "engines": [{"id": e.id, "serial": e.serial, "position": e.position, "source": e.source_dataset,
                                  "prediction": pred_out(latest.get(e.id))} for e in ac.engines]})
    return rows


@router.get("/aircraft")
def list_aircraft(search: str = Query("", max_length=32), state: str | None = None, trust: str | None = None,
                  db: Session = Depends(get_db), _: User = Depends(require("read"))):
    rows = _fleet_rows(db)
    s = search.strip().upper()
    rows = [r for r in rows if (not s or s in r["tail"] or any(s in e["serial"] for e in r["engines"]))
            and (not state or r["maintenance_state"] == state)
            and (not trust or any((e["prediction"] or {}).get("state") == trust for e in r["engines"]))]
    return {"items": rows, "total": len(rows), "limit": len(rows), "offset": 0}


@router.get("/aircraft/{aircraft_id}")
def aircraft_detail(aircraft_id: int, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    ac = db.get(Aircraft, aircraft_id)
    if not ac:
        raise HTTPException(404, "Aircraft not found")
    row = next(r for r in _fleet_rows(db) if r["id"] == ac.id)
    latest = fleet.latest_predictions(db)
    for e in row["engines"]:
        e["prediction"] = pred_out(latest.get(e["id"]), full=True)
    row["work_orders"] = [wo_out(w) for w in db.scalars(select(WorkOrder).where(WorkOrder.aircraft_id == ac.id)
                                                        .order_by(WorkOrder.due_at))]
    row["maintenance_records"] = [
        {"id": m.id, "performed_at": iso(m.performed_at), "record_type": m.record_type, "description": m.description,
         "engine_id": m.engine_id, "performed_by": m.performed_by, "source": f"{m.source_system}/{m.source_record_id}"}
        for m in db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.aircraft_id == ac.id)
                            .order_by(MaintenanceRecord.performed_at.desc()))]
    row["recommendations"] = [
        {"id": r.id, "engine_id": r.engine_id, "action": r.action, "priority": r.priority, "rationale": r.rationale,
         "status": r.status, "created_at": iso(r.created_at), "prediction_id": r.prediction_id}
        for r in db.scalars(select(Recommendation).where(Recommendation.aircraft_id == ac.id,
                                                         Recommendation.scenario_run_id.is_(None))
                            .order_by(Recommendation.id.desc()))]
    return row


@router.get("/engines/{engine_id}/readings")
def engine_readings(engine_id: int, last: int = Query(400, ge=1, le=2000), db: Session = Depends(get_db),
                    _: User = Depends(require("read"))):
    if not db.get(Engine, engine_id):
        raise HTTPException(404, "Engine not found")
    rows = db.scalars(select(SensorReading).where(SensorReading.engine_id == engine_id)
                      .order_by(SensorReading.cycle.desc()).limit(last)).all()
    m = load_model()
    return {"engine_id": engine_id, "sensors": {s: dict(zip(["symbol", "description", "unit"], m.bundle["sensor_meta"][s]))
                                                for s in m.sensors},
            "readings": [{"cycle": r.cycle, "recorded_at": iso(r.recorded_at), **r.values} for r in reversed(rows)]}


@router.get("/engines/{engine_id}/predictions")
def engine_predictions(engine_id: int, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    rows = db.scalars(select(Prediction).where(Prediction.engine_id == engine_id, Prediction.scenario_run_id.is_(None))
                      .order_by(Prediction.id.desc()).limit(100)).all()
    return {"items": [pred_out(p) for p in rows]}


@router.post("/engines/{engine_id}/predict")
def predict_engine(engine_id: int, db: Session = Depends(get_db), user: User = Depends(require("scenario:run"))):
    eng = db.get(Engine, engine_id)
    if not eng:
        raise HTTPException(404, "Engine not found")
    p = fleet.refresh_engine(db, eng)
    audit(db, user.username, "prediction.run", "engine", eng.serial, {"prediction_id": p.id, "state": p.state,
                                                                       "model_version": p.model_version})
    db.commit()
    return pred_out(p, full=True)


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: int, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    p = db.get(Prediction, prediction_id)
    if not p:
        raise HTTPException(404, "Prediction not found")
    return pred_out(p, full=True)


@router.get("/fleet/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    rows = _fleet_rows(db)
    preds = [e["prediction"] for r in rows for e in r["engines"] if e["prediction"]]
    wos = db.scalars(select(WorkOrder).where(WorkOrder.status.in_(OPEN), WorkOrder.approval_state != "rejected")).all()
    parts = parts_view(db)
    sim = db.scalar(select(ScenarioRun).where(ScenarioRun.kind == "policy_comparison").order_by(ScenarioRun.id.desc()))
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(8)).all()
    pending_recs = db.scalars(select(Recommendation).where(Recommendation.status == "proposed",
                                                           Recommendation.scenario_run_id.is_(None))).all()
    latest = max(preds, key=lambda p: p["created_at"]) if preds else None
    return {
        "aircraft_total": len(rows), "engines_total": sum(len(r["engines"]) for r in rows),
        "maintenance_states": dict(Counter(r["maintenance_state"] for r in rows)),
        "trust_states": dict(Counter(p["state"] for p in preds)),
        "warnings": [{"aircraft_id": r["id"], "tail": r["tail"], "state": r["maintenance_state"],
                      "engines": [{"serial": e["serial"], "state": (e["prediction"] or {}).get("state"),
                                   "rul_lower": (e["prediction"] or {}).get("rul_lower")} for e in r["engines"]]}
                     for r in rows if r["maintenance_state"] in ("action_required", "watch")],
        "outstanding_inspections": sum(1 for w in wos if w.task_type == "inspection"),
        "pending_recommendations": len(pending_recs),
        "workload": {"open_work_orders": len(wos), "planned_hours": sum(w.duration_hours for w in wos),
                     "pending_approval": sum(1 for w in wos if w.approval_state == "pending"),
                     "by_skill": dict(Counter(w.required_skill for w in wos))},
        "parts_shortages": [p for p in parts if p["shortage"]],
        "latest_prediction": latest,
        "recent_events": [{"id": e.id, "at": iso(e.created_at), "actor": e.actor, "action": e.action,
                           "entity": f"{e.entity_type}:{e.entity_id}"} for e in events],
        "simulated_availability": None if not sim else {
            "label": sim.result["label"], "run_id": sim.id, "seed": sim.seed,
            "reactive": sim.result["reactive"]["daily_availability_pct"],
            "predictive": sim.result["predictive"]["daily_availability_pct"]},
        "data_note": "Synthetic demo fleet; engine sensor streams replay NASA C-MAPSS FD001 hold-out trajectories.",
    }
