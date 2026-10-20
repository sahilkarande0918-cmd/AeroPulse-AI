from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import Page, iso, paginate
from app.api.maintenance import decision_out
from app.database import get_db
from app.models import Decision, Recommendation, ScenarioRun, Schedule, User
from app.security import audit, require
from app.services import simulator, trusttwin
from ml.inference import load_model

router = APIRouter(tags=["trusttwin"])


def run_out(r: ScenarioRun, db: Session) -> dict:
    out = {"id": r.id, "kind": r.kind, "created_at": iso(r.created_at), "seed": r.seed, "params": r.params,
           "result": r.result, "result_hash": r.result_hash}
    if r.kind == "trusttwin":
        rec = db.scalar(select(Recommendation).where(Recommendation.scenario_run_id == r.id))
        scheds = db.scalars(select(Schedule).where(Schedule.scenario_run_id == r.id).order_by(Schedule.id)).all()
        ids = {"recommendation": [rec.id] if rec else [], "schedule": [s.id for s in scheds]}
        decisions = db.scalars(select(Decision).where(
            ((Decision.target_type == "recommendation") & Decision.target_id.in_(ids["recommendation"] or [-1]))
            | ((Decision.target_type == "schedule") & Decision.target_id.in_(ids["schedule"] or [-1])))
            .order_by(Decision.id)).all()
        out["review"] = {
            "recommendation": rec and {"id": rec.id, "status": rec.status, "action": rec.action, "priority": rec.priority,
                                       "rationale": rec.rationale},
            "schedules": [{"id": s.id, "solver": s.solver, "status": s.status} for s in scheds],
            "decisions": [decision_out(d) for d in decisions],
        }
    return out


@router.post("/trusttwin/scenarios", status_code=201)
def run_scenario(body: trusttwin.ScenarioParams, db: Session = Depends(get_db), user: User = Depends(require("scenario:run"))):
    m = load_model()
    bad = [s for s in [*body.dropout_sensors, *( [body.bias_sensor] if body.bias_sensor else [])] if s not in m.sensors]
    if bad:
        raise HTTPException(422, f"Unknown or non-model sensors: {bad}. Model sensors: {m.sensors}")
    try:
        r = trusttwin.run(db, body, user.id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from None
    audit(db, user.username, "scenario.run", "scenario_run", r.id,
          {"engine_id": body.engine_id, "seed": body.seed, "result_hash": r.result_hash,
           "baseline_state": r.result["baseline"]["assessment"]["state"],
           "revised_state": r.result["revised"]["assessment"]["state"]})
    db.commit()
    return run_out(r, db)


@router.get("/trusttwin/scenarios")
def list_scenarios(page: Page = Depends(), db: Session = Depends(get_db), _: User = Depends(require("read"))):
    q = select(ScenarioRun).where(ScenarioRun.kind == "trusttwin").order_by(ScenarioRun.id.desc())
    return paginate(db, q, page, lambda r: {
        "id": r.id, "created_at": iso(r.created_at), "seed": r.seed, "params": r.params, "result_hash": r.result_hash,
        "engine": r.result["engine"], "baseline_state": r.result["baseline"]["assessment"]["state"],
        "revised_state": r.result["revised"]["assessment"]["state"],
        "kpis": {"baseline": r.result["baseline"]["plan"]["kpis"], "revised": r.result["revised"]["plan"]["kpis"]}})


@router.get("/trusttwin/scenarios/{run_id}")
def get_scenario(run_id: int, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    r = db.get(ScenarioRun, run_id)
    if not r:
        raise HTTPException(404, "Scenario run not found")
    return run_out(r, db)


class SimIn(BaseModel):
    seed: int = Field(2026, ge=0, le=2**31)
    days: int = Field(120, ge=10, le=365)
    n_aircraft: int = Field(10, ge=1, le=40)
    crews: int = Field(2, ge=1, le=10)
    spare_engines: int = Field(4, ge=0, le=50)
    resupply_every_days: int = Field(14, ge=1, le=120)
    resupply_qty: int = Field(3, ge=0, le=20)
    part_delay_prob: float = Field(0.3, ge=0, le=1)
    dropout_prob: float = Field(0.02, ge=0, le=0.5)
    absence_prob: float = Field(0.05, ge=0, le=1)
    review_delay_days: int = Field(1, ge=0, le=14)
    trigger_lower_bound: int = Field(25, ge=0, le=125)
    hold_lower_bound: int = Field(6, ge=0, le=125)


@router.post("/simulation/compare", status_code=201)
def compare(body: SimIn, db: Session = Depends(get_db), user: User = Depends(require("scenario:run"))):
    res = simulator.compare(simulator.SimParams(**body.model_dump()))
    r = ScenarioRun(kind="policy_comparison", user_id=user.id, seed=body.seed, params=res["params"], result=res,
                    result_hash=res["result_hash"])
    db.add(r)
    db.flush()
    audit(db, user.username, "simulation.compare", "scenario_run", r.id, {"seed": body.seed, "result_hash": r.result_hash})
    db.commit()
    return run_out(r, db)


@router.get("/simulation/latest")
def latest_sim(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    r = db.scalar(select(ScenarioRun).where(ScenarioRun.kind == "policy_comparison").order_by(ScenarioRun.id.desc()))
    if not r:
        raise HTTPException(404, "No simulation has been run")
    return run_out(r, db)
