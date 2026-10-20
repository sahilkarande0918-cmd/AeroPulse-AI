import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import Page, iso, paginate
from app.database import get_db
from app.models import AuditEvent, Decision, Engine, Prediction, Recommendation, ScenarioRun, User
from app.security import require, verify_audit_chain

router = APIRouter(tags=["reports"])


def audit_out(e: AuditEvent) -> dict:
    return {"id": e.id, "created_at": iso(e.created_at), "actor": e.actor, "action": e.action,
            "entity_type": e.entity_type, "entity_id": e.entity_id, "details": e.details, "hash": e.hash}


@router.get("/audit")
def list_audit(entity_type: str | None = None, actor: str | None = None, page: Page = Depends(),
               db: Session = Depends(get_db), _: User = Depends(require("audit:read"))):
    q = select(AuditEvent).order_by(AuditEvent.id.desc())
    if entity_type:
        q = q.where(AuditEvent.entity_type == entity_type)
    if actor:
        q = q.where(AuditEvent.actor == actor)
    return paginate(db, q, page, audit_out)


@router.get("/audit/verify")
def verify(db: Session = Depends(get_db), _: User = Depends(require("audit:read"))):
    return {**verify_audit_chain(db),
            "note": "SHA-256 hash chain detects edits/deletions of individual events; a database administrator "
                    "could still rewrite the whole chain, so this is tamper-evident, not tamper-proof."}


def _recommendation_rows(db: Session) -> list[dict]:
    recs = db.scalars(select(Recommendation).order_by(Recommendation.id)).all()
    preds = {p.id: p for p in db.scalars(select(Prediction).where(Prediction.id.in_([r.prediction_id for r in recs])))}
    engines = {e.id: e for e in db.scalars(select(Engine))}
    decisions: dict[int, list[Decision]] = {}
    for d in db.scalars(select(Decision).where(Decision.target_type == "recommendation").order_by(Decision.id)):
        decisions.setdefault(d.target_id, []).append(d)
    rows = []
    for r in recs:
        p, e, ds = preds[r.prediction_id], engines[r.engine_id], decisions.get(r.id, [])
        rows.append({"recommendation_id": r.id, "created_at": iso(r.created_at), "aircraft": e.aircraft.tail,
                     "engine": e.serial, "action": r.action, "priority": r.priority, "status": r.status,
                     "trust_state": p.state, "rul": None if p.rul is None else round(p.rul, 1),
                     "rul_lower": None if p.rul_lower is None else round(p.rul_lower, 1),
                     "rul_upper": None if p.rul_upper is None else round(p.rul_upper, 1),
                     "model_version": p.model_version, "data_source": e.source_dataset,
                     "scenario_run_id": r.scenario_run_id or "",
                     "decided_by": "; ".join(d.user.username for d in ds), "decision": "; ".join(d.decision for d in ds),
                     "decision_reason": "; ".join(d.reason for d in ds),
                     "decided_at": "; ".join(iso(d.created_at) for d in ds), "rationale": r.rationale})
    return rows


@router.get("/reports/recommendations")
def recommendations_report(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    rows = _recommendation_rows(db)
    return {"items": rows, "total": len(rows)}


def _csv(rows: list[dict], name: str) -> StreamingResponse:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:  # neutralise spreadsheet formula injection
            w.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in r.items()})
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/{name}.csv")
def export_csv(name: str, db: Session = Depends(get_db), user: User = Depends(require("read"))):
    if name == "recommendations":
        return _csv(_recommendation_rows(db), "aeropulse_recommendations.csv")
    if name in ("audit", "decisions", "scenarios") and user.role not in ("admin", "officer", "analyst"):
        raise HTTPException(403, "Role lacks permission 'audit:read'")
    if name == "audit":
        return _csv([{**audit_out(e), "details": str(e.details)} for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id))],
                    "aeropulse_audit.csv")
    if name == "decisions":
        return _csv([{"id": d.id, "created_at": iso(d.created_at), "target_type": d.target_type, "target_id": d.target_id,
                      "decision": d.decision, "reason": d.reason, "user": d.user.username, "role": d.user.role}
                     for d in db.scalars(select(Decision).order_by(Decision.id))], "aeropulse_decisions.csv")
    if name == "scenarios":
        rows = []
        for r in db.scalars(select(ScenarioRun).order_by(ScenarioRun.id)):
            base = {"id": r.id, "kind": r.kind, "created_at": iso(r.created_at), "seed": r.seed, "result_hash": r.result_hash}
            if r.kind == "trusttwin":
                b, v = r.result["baseline"], r.result["revised"]
                base.update(engine=r.result["engine"]["serial"], baseline_state=b["assessment"]["state"],
                            revised_state=v["assessment"]["state"], baseline_objective=b["plan"]["objective"],
                            revised_objective=v["plan"]["objective"], revised_unscheduled=v["plan"]["kpis"]["unscheduled"])
            else:
                base.update(engine="fleet", baseline_state="reactive", revised_state="predictive",
                            baseline_objective=r.result["reactive"]["metrics"]["availability_pct"],
                            revised_objective=r.result["predictive"]["metrics"]["availability_pct"], revised_unscheduled="")
            rows.append(base)
        return _csv(rows, "aeropulse_scenarios.csv")
    raise HTTPException(404, "Unknown report")
