from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import Page, iso, paginate
from app.database import get_db, utcnow
from app.models import Decision, MaintenanceRecord, Part, Recommendation, Schedule, Technician, User, WorkOrder
from app.security import audit, require
from app.services import fleet, planner

router = APIRouter(tags=["maintenance"])


def wo_out(w: WorkOrder) -> dict:
    return {"id": w.id, "code": w.code, "aircraft_id": w.aircraft_id, "aircraft": w.aircraft.tail, "engine_id": w.engine_id,
            "title": w.title, "task_type": w.task_type, "required_skill": w.required_skill,
            "duration_hours": w.duration_hours, "priority": w.priority, "due_at": iso(w.due_at), "status": w.status,
            "approval_state": w.approval_state, "predecessors": w.predecessor_codes, "parts": w.parts,
            "planned_start": iso(w.planned_start), "assigned_technician": w.assigned_technician,
            "source": w.source, "external_id": w.external_id, "created_at": iso(w.created_at)}


def schedule_out(s: Schedule, full: bool = True) -> dict:
    out = {"id": s.id, "created_at": iso(s.created_at), "solver": s.solver, "status": s.status,
           "horizon_start": iso(s.horizon_start), "input_hash": s.input_hash, "scenario_run_id": s.scenario_run_id,
           "kpis": s.result.get("kpis"), "objective": s.result.get("objective"), "solver_status": s.result.get("status")}
    if full:
        out.update(assignments=s.result["assignments"], unscheduled=s.result["unscheduled"],
                   technicians=[t["id"] for t in s.result.get("problem", {}).get("techs", [])],
                   blocked={t["id"]: t["blocked"] for t in s.result.get("problem", {}).get("techs", [])})
    return out


def decision_out(d: Decision) -> dict:
    return {"id": d.id, "target_type": d.target_type, "target_id": d.target_id, "decision": d.decision, "reason": d.reason,
            "user": d.user.username, "role": d.user.role, "created_at": iso(d.created_at)}


# ----------------------------------------------------------------------------------- work orders
@router.get("/work-orders")
def list_work_orders(status: str | None = None, approval_state: str | None = None, aircraft_id: int | None = None,
                     page: Page = Depends(), db: Session = Depends(get_db), _: User = Depends(require("read"))):
    q = select(WorkOrder).order_by(WorkOrder.priority, WorkOrder.due_at)
    if status:
        q = q.where(WorkOrder.status == status)
    if approval_state:
        q = q.where(WorkOrder.approval_state == approval_state)
    if aircraft_id:
        q = q.where(WorkOrder.aircraft_id == aircraft_id)
    return paginate(db, q, page, wo_out)


class ProgressIn(BaseModel):
    status: Literal["in_progress", "done", "cancelled"]
    note: str = Field("", max_length=500)


@router.patch("/work-orders/{code}/progress")
def progress(code: str, body: ProgressIn, db: Session = Depends(get_db), user: User = Depends(require("workorder:progress"))):
    w = db.scalar(select(WorkOrder).where(WorkOrder.code == code))
    if not w:
        raise HTTPException(404, "Work order not found")
    if w.approval_state != "approved":
        raise HTTPException(409, "Work order must be approved before work starts")
    if body.status == "cancelled" and user.role == "technician":
        raise HTTPException(403, "Technicians cannot cancel work orders")
    allowed = {"open": {"in_progress", "cancelled"}, "scheduled": {"in_progress", "cancelled"},
               "in_progress": {"done", "cancelled"}}
    if body.status not in allowed.get(w.status, set()):
        raise HTTPException(409, f"Cannot move work order from {w.status} to {body.status}")
    before = w.status
    w.status = body.status
    if body.status == "done":
        db.add(MaintenanceRecord(aircraft_id=w.aircraft_id, engine_id=w.engine_id, performed_at=utcnow(),
                                 record_type={"inspection": "inspection", "replacement": "replacement"}.get(w.task_type, "servicing"),
                                 description=f"{w.title} (closed {w.code}). {body.note}".strip(), performed_by=user.username,
                                 source_system="AEROPULSE", source_record_id=w.code))
        for x in w.parts:  # consume stock on completion
            p = db.scalar(select(Part).where(Part.part_number == x["part_number"]))
            if p:
                p.on_hand = max(0, p.on_hand - int(x["qty"]))
    audit(db, user.username, "work_order.progress", "work_order", w.code, {"from": before, "to": body.status, "note": body.note})
    db.commit()
    return wo_out(w)


# ----------------------------------------------------------------------------------- technicians
@router.get("/technicians")
def list_technicians(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    return {"items": [{"code": t.code, "name": t.name, "skills": t.skills, "shift": f"{t.shift_start_hour:02d}:00-{t.shift_end_hour:02d}:00 IST",
                       "available": t.available, "unavailable": t.unavailable}
                      for t in db.scalars(select(Technician).order_by(Technician.code))]}


class TechPatch(BaseModel):
    available: bool | None = None
    add_leave_start: datetime | None = None
    add_leave_end: datetime | None = None
    clear_leave: bool = False
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/technicians/{code}")
def update_technician(code: str, body: TechPatch, db: Session = Depends(get_db), user: User = Depends(require("plan"))):
    t = db.scalar(select(Technician).where(Technician.code == code))
    if not t:
        raise HTTPException(404, "Technician not found")
    if body.available is not None:
        t.available = body.available
    if body.clear_leave:
        t.unavailable = []
    if body.add_leave_start and body.add_leave_end:
        if body.add_leave_start.tzinfo is None or body.add_leave_end <= body.add_leave_start:
            raise HTTPException(422, "Leave needs timezone-aware start < end")
        t.unavailable = [*t.unavailable, {"start": body.add_leave_start.isoformat(), "end": body.add_leave_end.isoformat(),
                                          "reason": body.reason}]
    audit(db, user.username, "technician.update", "technician", code, body.model_dump(mode="json"))
    db.commit()
    return {"code": t.code, "available": t.available, "unavailable": t.unavailable}


# ----------------------------------------------------------------------------------- recommendations & decisions
@router.get("/recommendations")
def list_recommendations(status: str | None = None, include_scenarios: bool = False, page: Page = Depends(),
                         db: Session = Depends(get_db), _: User = Depends(require("read"))):
    q = select(Recommendation).order_by(Recommendation.id.desc())
    if status:
        q = q.where(Recommendation.status == status)
    if not include_scenarios:
        q = q.where(Recommendation.scenario_run_id.is_(None))

    def ser(r: Recommendation):
        return {"id": r.id, "prediction_id": r.prediction_id, "aircraft_id": r.aircraft_id, "engine_id": r.engine_id,
                "action": r.action, "priority": r.priority, "rationale": r.rationale, "status": r.status,
                "work_order_id": r.work_order_id, "scenario_run_id": r.scenario_run_id, "created_at": iso(r.created_at)}
    return paginate(db, q, page, ser)


class DecisionIn(BaseModel):
    target_type: Literal["recommendation", "schedule", "work_order"]
    target_id: int
    decision: Literal["approve", "reject", "request_inspection", "request_data"]
    reason: str = Field("", max_length=2000)


@router.post("/decisions", status_code=201)
def decide(body: DecisionIn, db: Session = Depends(get_db), user: User = Depends(require("approve"))):
    if body.decision != "approve" and len(body.reason.strip()) < 5:
        raise HTTPException(422, "A reason (min 5 characters) is required for rejections, overrides and requests")
    now = utcnow()
    effect: dict[str, object] = {}
    if body.target_type == "recommendation":
        r = db.get(Recommendation, body.target_id)
        if not r:
            raise HTTPException(404, "Recommendation not found")
        if r.status != "proposed":
            raise HTTPException(409, f"Recommendation already {r.status}")
        live = r.scenario_run_id is None
        if body.decision == "approve":
            r.status = "approved"
            if live:
                spec = next((s for s in fleet.ACTIONS.values() if s["action"] == r.action), fleet.ACTIONS["inspect"])
                wo = fleet.work_order_from_recommendation(db, r, {**spec, "due_days": 3 if r.priority > 1 else 1}, now)
                r.work_order_id = wo.id
                effect["work_order"] = wo.code
        elif body.decision == "reject":
            r.status = "rejected"
        elif body.decision == "request_inspection":
            r.status = "inspection_requested"
            if live:
                wo = fleet.work_order_from_recommendation(db, r, {**fleet.ACTIONS["inspect"], "due_days": 2}, now)
                r.work_order_id = wo.id
                effect["work_order"] = wo.code
        else:
            r.status = "info_requested"
        effect["live"] = live
    elif body.target_type == "schedule":
        s = db.get(Schedule, body.target_id)
        if not s:
            raise HTTPException(404, "Schedule not found")
        if s.status != "proposed":
            raise HTTPException(409, f"Schedule already {s.status}")
        if body.decision not in ("approve", "reject"):
            raise HTTPException(422, "Schedules can only be approved or rejected")
        s.status = "approved" if body.decision == "approve" else "rejected"
        effect["live"] = s.scenario_run_id is None
        if s.status == "approved" and s.scenario_run_id is None:
            for other in db.scalars(select(Schedule).where(Schedule.id != s.id, Schedule.scenario_run_id.is_(None),
                                                           Schedule.status.in_(("proposed", "approved")))):
                other.status = "superseded"
            wos = {w.code: w for w in db.scalars(select(WorkOrder))}
            for a in s.result["assignments"]:
                w = wos.get(a["task"])
                if w and w.status in ("open", "scheduled"):
                    w.status, w.assigned_technician = "scheduled", a["technician"]
                    w.planned_start = s.horizon_start + timedelta(hours=a["start"])
            effect["work_orders_scheduled"] = len(s.result["assignments"])
            effect["awaiting_work_order_approval"] = sum(1 for a in s.result["assignments"]
                                                         if a["task"] in wos and wos[a["task"]].approval_state == "pending")
    else:
        w = db.get(WorkOrder, body.target_id)
        if not w:
            raise HTTPException(404, "Work order not found")
        if w.approval_state != "pending":
            raise HTTPException(409, f"Work order already {w.approval_state}")
        if body.decision not in ("approve", "reject"):
            raise HTTPException(422, "Work orders can only be approved or rejected")
        w.approval_state = "approved" if body.decision == "approve" else "rejected"
    d = Decision(target_type=body.target_type, target_id=body.target_id, decision=body.decision,
                 reason=body.reason.strip() or "Approved after review", user_id=user.id)
    db.add(d)
    db.flush()
    audit(db, user.username, f"decision.{body.decision}", body.target_type, body.target_id,
          {"decision_id": d.id, "reason": d.reason, "effect": effect})
    db.commit()
    return {**decision_out(d), "effect": effect}


@router.get("/decisions")
def list_decisions(target_type: str | None = None, target_id: int | None = None, page: Page = Depends(),
                   db: Session = Depends(get_db), _: User = Depends(require("read"))):
    q = select(Decision).order_by(Decision.id.desc())
    if target_type:
        q = q.where(Decision.target_type == target_type)
    if target_id is not None:
        q = q.where(Decision.target_id == target_id)
    return paginate(db, q, page, decision_out)


# ----------------------------------------------------------------------------------- schedules
class ScheduleIn(BaseModel):
    solver: Literal["cp-sat", "greedy"] = "cp-sat"
    lateness_weight: int = Field(10, ge=0, le=1000)
    unscheduled_weight: int = Field(2000, ge=1, le=100000)
    completion_weight: int = Field(1, ge=0, le=100)


@router.post("/schedules", status_code=201)
def create_schedule(body: ScheduleIn, db: Session = Depends(get_db), user: User = Depends(require("plan"))):
    weights = {"lateness": body.lateness_weight, "unscheduled": body.unscheduled_weight, "completion": body.completion_weight}
    prob, t0, _ = fleet.build_problem(db, weights=weights)
    result = planner.solve_cpsat(prob) if body.solver == "cp-sat" else planner.solve_greedy(prob)
    result["weights"] = weights
    for old in db.scalars(select(Schedule).where(Schedule.scenario_run_id.is_(None), Schedule.status == "proposed")):
        old.status = "superseded"
    s = Schedule(created_by=user.id, solver=result["solver"], horizon_start=t0, input_hash=planner.problem_hash(prob), result=result)
    db.add(s)
    db.flush()
    audit(db, user.username, "schedule.propose", "schedule", s.id, {"solver": s.solver, "kpis": result["kpis"],
                                                                   "objective": result["objective"]})
    db.commit()
    return schedule_out(s)


@router.get("/schedules")
def list_schedules(include_scenarios: bool = False, page: Page = Depends(), db: Session = Depends(get_db),
                   _: User = Depends(require("read"))):
    q = select(Schedule).order_by(Schedule.id.desc())
    if not include_scenarios:
        q = q.where(Schedule.scenario_run_id.is_(None))
    return paginate(db, q, page, lambda s: schedule_out(s, full=False))


@router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: int, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    s = db.get(Schedule, schedule_id)
    if not s:
        raise HTTPException(404, "Schedule not found")
    return schedule_out(s)


@router.get("/maintenance-records")
def list_records(aircraft_id: int | None = Query(None), page: Page = Depends(), db: Session = Depends(get_db),
                 _: User = Depends(require("read"))):
    q = select(MaintenanceRecord).order_by(MaintenanceRecord.performed_at.desc())
    if aircraft_id:
        q = q.where(MaintenanceRecord.aircraft_id == aircraft_id)
    return paginate(db, q, page, lambda m: {"id": m.id, "aircraft_id": m.aircraft_id, "engine_id": m.engine_id,
                                            "performed_at": iso(m.performed_at), "record_type": m.record_type,
                                            "description": m.description, "performed_by": m.performed_by,
                                            "source": f"{m.source_system}/{m.source_record_id}", "batch_id": m.batch_id})
