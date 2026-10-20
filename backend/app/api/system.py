import json
from typing import Literal

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import DEFAULT_TRUST_THRESHOLDS, settings
from app.database import get_db
from app.models import AppSetting, IngestionBatch, Prediction, ScenarioRun, SensorReading, User
from app.security import ROLES, audit, require
from app.services import copilot, fleet
from ml.inference import ARTIFACT_DIR, load_model

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok, model_ok = True, True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        version = load_model().version
    except FileNotFoundError:
        model_ok, version = False, None
    return {"status": "ok" if db_ok and model_ok else "degraded", "database": db_ok, "model_loaded": model_ok,
            "model_version": version}


@router.get("/system/status")
def status(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    batches = db.execute(select(IngestionBatch.source_type, IngestionBatch.source_name, func.count(), func.max(IngestionBatch.created_at))
                         .group_by(IngestionBatch.source_type, IngestionBatch.source_name)).all()
    return {
        "app_env": settings.app_env, "mode": "production" if settings.is_production else "demo",
        "database_dialect": db.get_bind().dialect.name,
        "offline_capable": True,
        "external_calls": ["Gemini API (only when LLM_ENABLED=true)"] if copilot.enabled() else [],
        "llm_enabled": copilot.enabled(),
        "data_sources": [
            {"name": "NASA C-MAPSS FD001 hold-out replay", "type": "sensor", "kind": "public simulated dataset",
             "records": db.scalar(select(func.count(SensorReading.id)).where(SensorReading.batch_id.is_(None)))},
            {"name": "SYNTH-CAMO / SYNTH-TECHLOG", "type": "work orders, records, parts, technicians", "kind": "synthetic demo"},
            *[{"name": n, "type": t, "kind": "ingested", "batches": c, "last_import": m.isoformat() if m else None}
              for t, n, c, m in batches],
        ],
        "predictions_stored": db.scalar(select(func.count(Prediction.id))),
        "scenario_runs": db.scalar(select(func.count(ScenarioRun.id))),
    }


@router.get("/model")
def model_info(_: User = Depends(require("read"))):
    report = json.loads((ARTIFACT_DIR / "evaluation_report.json").read_text())
    schema = json.loads((ARTIFACT_DIR / "feature_schema.json").read_text())
    return {"report": report, "feature_schema": schema}


@router.get("/model/drift")
def drift(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    """Fleet sensor distribution vs training (fit engines): standardised mean shift and out-of-range share."""
    m = load_model()
    vals: dict[str, list[float]] = {s: [] for s in m.sensors}
    for (v,) in db.execute(select(SensorReading.values)):
        for s in m.sensors:
            if v.get(s) is not None:
                vals[s].append(float(v[s]))
    rows = []
    for s in m.sensors:
        st, x = m.sensor_stats[s], np.array(vals[s])
        if not len(x):
            continue
        shift = (x.mean() - st["mean"]) / (st["std"] or 1)
        out = float(np.mean((x < st["min"]) | (x > st["max"])))
        rows.append({"sensor": s, "symbol": m.bundle["sensor_meta"][s][0], "n": int(len(x)), "train_mean": st["mean"],
                     "fleet_mean": float(x.mean()), "std_shift": round(float(shift), 3), "out_of_range_share": round(out, 4),
                     "flag": abs(shift) > 1 or out > 0.05})
    return {"method": "Standardised mean shift and share outside training min-max per sensor (fleet readings vs fit engines). "
                      "Evidently not used: two summary statistics suffice for the prototype.", "sensors": rows}


@router.get("/settings/thresholds")
def get_thresholds(db: Session = Depends(get_db), _: User = Depends(require("read"))):
    return {"thresholds": fleet.thresholds(db), "defaults": DEFAULT_TRUST_THRESHOLDS,
            "note": "Prototype settings - not certified aircraft maintenance standards."}


class ThresholdsIn(BaseModel):
    thresholds: dict[str, float]
    reason: str = Field(min_length=5, max_length=500)


@router.put("/settings/thresholds")
def put_thresholds(body: ThresholdsIn, db: Session = Depends(get_db), user: User = Depends(require("admin"))):
    unknown = set(body.thresholds) - set(DEFAULT_TRUST_THRESHOLDS)
    if unknown or any(v < 0 for v in body.thresholds.values()):
        raise HTTPException(422, f"Unknown keys {sorted(unknown)} or negative values")
    row = db.get(AppSetting, "trust_thresholds") or AppSetting(key="trust_thresholds", value={})
    before = dict(row.value)
    row.value = {**before, **body.thresholds}
    db.merge(row)
    audit(db, user.username, "settings.thresholds", "settings", "trust_thresholds",
          {"before": before, "after": row.value, "reason": body.reason})
    db.commit()
    return {"thresholds": fleet.thresholds(db)}


@router.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(require("admin"))):
    return {"items": [{"username": u.username, "full_name": u.full_name, "role": u.role, "active": u.active}
                      for u in db.scalars(select(User).order_by(User.username))], "roles": ROLES}


class UserPatch(BaseModel):
    role: Literal["admin", "officer", "technician", "analyst"] | None = None
    active: bool | None = None


@router.patch("/users/{username}")
def patch_user(username: str, body: UserPatch, db: Session = Depends(get_db), admin: User = Depends(require("admin"))):
    u = db.scalar(select(User).where(User.username == username))
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(409, "Administrators cannot change their own role or status")
    before = {"role": u.role, "active": u.active}
    if body.role:
        u.role = body.role
    if body.active is not None:
        u.active = body.active
    audit(db, admin.username, "user.update", "user", username, {"before": before, "after": {"role": u.role, "active": u.active}})
    db.commit()
    return {"username": u.username, "role": u.role, "active": u.active}


class CopilotIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    prediction_id: int | None = None
    scenario_run_id: int | None = None


@router.post("/copilot/explain")
def copilot_explain(body: CopilotIn, db: Session = Depends(get_db), _: User = Depends(require("read"))):
    if not copilot.enabled():
        raise HTTPException(503, "Copilot disabled (no LLM configured). The platform runs fully without it.")
    facts = {}
    if body.prediction_id and (p := db.get(Prediction, body.prediction_id)):
        facts["prediction"] = {"state": p.state, "rul": p.rul, "rul_lower": p.rul_lower, "rul_upper": p.rul_upper,
                               "checks": p.quality.get("checks"), "evidence": p.evidence, "model_version": p.model_version}
    if body.scenario_run_id and (r := db.get(ScenarioRun, body.scenario_run_id)):
        facts["scenario"] = {"explanation": r.result.get("explanation"), "diff": r.result.get("diff")}
    if not facts:
        raise HTTPException(422, "Provide a prediction_id or scenario_run_id to ground the explanation")
    try:
        return {"answer": copilot.explain(body.question, facts), "grounded_on": list(facts),
                "disclaimer": "LLM-generated wording of stored results; verify against the source data."}
    except Exception:
        raise HTTPException(503, "Copilot request failed") from None
