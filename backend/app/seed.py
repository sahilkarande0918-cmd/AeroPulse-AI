"""Seed an explicitly SYNTHETIC demo fleet. Engine sensor streams replay real NASA C-MAPSS FD001
hold-out trajectories; aircraft, people, parts, work orders and records are fictional.

    python -m app.seed      (idempotent: does nothing if users exist)
"""
import hashlib
import json
import secrets
from datetime import timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import log, settings
from app.database import SessionLocal, utcnow
from app.models import Aircraft, Engine, MaintenanceRecord, Part, ScenarioRun, SensorReading, Technician, User, WorkOrder
from app.security import audit, hash_password
from app.services import fleet, simulator
from ml.inference import ARTIFACT_DIR, load_model

# Target true remaining cycles per engine slot: a deliberate spread of health states for the demo.
TARGET_REMAINING = [14, 95, 38, 120, 70, 55, 150, 85, 30, 100, 65, 130, 45, 110, 80, 22, 125, 90, -12, 105]


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        log.info("seed: database already populated, skipping")
        return
    now = utcnow()
    pw = settings.demo_password or secrets.token_urlsafe(10)
    for u, name, role in [("admin", "Demo Administrator", "admin"), ("officer", "Demo Maintenance Officer", "officer"),
                          ("technician", "Demo Technician", "technician"), ("analyst", "Demo Analyst", "analyst")]:
        db.add(User(username=u, full_name=name, role=role, password_hash=hash_password(pw)))
    if not settings.demo_password:
        log.warning("seed: DEMO_PASSWORD not set; generated demo password for all demo users: %s", pw)

    raw = pd.read_csv(ARTIFACT_DIR / "holdout_trajectories.csv.gz")
    units = sorted(raw.unit.unique())
    sensors = [f"s{i}" for i in range(1, 22)]
    aircraft = []
    for k in range(10):
        ac = Aircraft(tail=f"AP-{101 + k}", type_name="Fictional twin-engine trainer (synthetic)",
                      base="Demo Base North" if k < 5 else "Demo Base South")
        db.add(ac)
        aircraft.append(ac)
    db.flush()
    for slot, unit in enumerate(units[:20]):
        ac = aircraft[slot // 2]
        eng = Engine(serial=f"AP-ENG-{slot + 1:02d}", aircraft_id=ac.id, position=slot % 2 + 1,
                     source_dataset="NASA C-MAPSS FD001 (hold-out)", source_unit=int(unit))
        db.add(eng)
        db.flush()
        traj = raw[raw.unit == unit]
        length = int(traj.cycle.max())
        target = TARGET_REMAINING[slot]
        current = 12 if target < 0 else max(25, length - target)   # negative target = newly installed engine
        lag_h = 120 if ac.tail == "AP-107" else 2 + slot % 5       # AP-107: data link down for 5 days
        rows = traj[traj.cycle <= current].to_dict("records")
        for r in rows:
            vals = {s: float(r[s]) for s in sensors}
            if eng.serial == "AP-ENG-08" and r["cycle"] > current - 2:   # sensor dropout on latest readings
                vals.pop("s11"); vals.pop("s7")
            db.add(SensorReading(engine_id=eng.id, cycle=int(r["cycle"]), values=vals,
                                 recorded_at=now - timedelta(hours=lag_h + fleet.HOURS_PER_CYCLE * (current - r["cycle"]))))
    db.flush()

    techs = [("TECH-01", "Powerplant Tech 1", ["powerplant", "ndt"], 8, 16), ("TECH-02", "Powerplant Tech 2", ["powerplant"], 8, 16),
             ("TECH-03", "Powerplant Tech 3", ["powerplant"], 14, 22), ("TECH-04", "NDT Inspector 1", ["ndt"], 8, 16),
             ("TECH-05", "Avionics Tech 1", ["avionics"], 8, 16), ("TECH-06", "Avionics/Airframe Tech", ["avionics", "airframe"], 14, 22)]
    for code, name, skills, s, e in techs:
        leave = [{"start": (now + timedelta(days=3)).isoformat(), "end": (now + timedelta(days=5)).isoformat(),
                  "reason": "scheduled leave"}] if code == "TECH-02" else []
        db.add(Technician(code=code, name=name, skills=skills, shift_start_hour=s, shift_end_hour=e, unavailable=leave))

    parts = [("APX-HPT-MOD-KIT", "Hot-section module kit (fictional)", 1, 2, 2, 6, 45),
             ("APX-BORESCOPE-SEAL", "Borescope port seal set (fictional)", 6, 4, 10, 12, 10),
             ("APX-FUEL-NOZZLE", "Fuel nozzle assembly (fictional)", 4, 4, 4, 10, 30),
             ("APX-T50-PROBE", "LPT exit temperature probe (fictional)", 0, 2, 2, 3, 20),
             ("APX-OIL-FILTER", "Engine oil filter element (fictional)", 20, 10, 0, None, 7),
             ("APX-HYD-SEAL-KIT", "Hydraulic actuator seal kit (fictional)", 3, 2, 0, None, 14),
             ("APX-AV-HARNESS", "Sensor wiring harness segment (fictional)", 2, 1, 2, 8, 21)]
    for pn, name, on_hand, thr, rq, eta_d, lead in parts:
        db.add(Part(part_number=pn, name=name, on_hand=on_hand, reorder_threshold=thr, replenishment_qty=rq,
                    replenishment_eta=now + timedelta(days=eta_d) if eta_d else None, lead_time_days=lead))

    t = {a.tail: a for a in aircraft}
    wos = [  # code, tail, title, type, skill, hours, prio, due_days, approval, parts, preds
        ("WO-0001", "AP-103", "Troubleshoot intermittent LPT exit temperature indication", "troubleshooting", "avionics", 3, 2, 2, "approved", [], []),
        ("WO-0002", "AP-103", "Replace LPT exit temperature probe", "replacement", "powerplant", 4, 2, 3, "approved", [("APX-T50-PROBE", 1)], ["WO-0001"]),
        ("WO-0003", "AP-102", "Scheduled 200-cycle engine servicing", "servicing", "powerplant", 6, 3, 6, "approved", [("APX-OIL-FILTER", 2)], []),
        ("WO-0004", "AP-105", "Fuel nozzle flow check and replacement", "replacement", "powerplant", 6, 2, 4, "pending", [("APX-FUEL-NOZZLE", 2)], []),
        ("WO-0005", "AP-106", "Hydraulic actuator seal leak rectification", "replacement", "airframe", 5, 2, 3, "approved", [("APX-HYD-SEAL-KIT", 1)], []),
        ("WO-0006", "AP-108", "Routine borescope inspection (calendar)", "inspection", "ndt", 4, 3, 7, "approved", [("APX-BORESCOPE-SEAL", 1)], []),
        ("WO-0007", "AP-110", "Sensor harness chafing inspection", "inspection", "avionics", 2, 3, 5, "pending", [], []),
        ("WO-0008", "AP-110", "Replace chafed sensor harness segment", "replacement", "avionics", 4, 3, 6, "pending", [("APX-AV-HARNESS", 1)], ["WO-0007"]),
        ("WO-0009", "AP-104", "Scheduled 200-cycle engine servicing", "servicing", "powerplant", 6, 4, 9, "approved", [("APX-OIL-FILTER", 2)], []),
    ]
    for code, tail, title, ttype, skill, hrs, prio, due, appr, wparts, preds in wos:
        db.add(WorkOrder(code=code, aircraft_id=t[tail].id, title=title, task_type=ttype, required_skill=skill,
                         duration_hours=hrs, priority=prio, due_at=now + timedelta(days=due), approval_state=appr,
                         parts=[{"part_number": p, "qty": q} for p, q in wparts], predecessor_codes=preds,
                         source="SYNTH-CAMO", external_id=code))
    recs = [("AP-101", "inspection", "Borescope inspection, no findings", 40), ("AP-101", "servicing", "Oil filter change", 25),
            ("AP-102", "defect", "EGT spread reported by aircrew; trend monitoring raised", 12),
            ("AP-103", "defect", "Intermittent LPT exit temperature indication", 3),
            ("AP-104", "repair", "Bleed valve actuator replaced", 60), ("AP-105", "inspection", "Fuel nozzle spray pattern marginal", 5),
            ("AP-106", "defect", "Hydraulic seep at actuator", 2), ("AP-107", "servicing", "Data acquisition unit reset", 6),
            ("AP-108", "inspection", "Borescope inspection, minor coating loss HPT stage 1", 90),
            ("AP-110", "replacement", "Engine #1 replaced (newly installed engine)", 7),
            ("AP-110", "inspection", "Harness chafing suspected", 1), ("AP-109", "servicing", "Starter air valve sluggish; monitor", 4)]
    for n, (tail, rtype, desc, days_ago) in enumerate(recs, start=1):
        db.add(MaintenanceRecord(aircraft_id=t[tail].id, performed_at=now - timedelta(days=days_ago), record_type=rtype,
                                 description=desc, performed_by="Synthetic record", source_system="SYNTH-TECHLOG",
                                 source_record_id=f"TL-{n:04d}"))
    db.flush()
    for eng in db.scalars(select(Engine)):
        fleet.refresh_engine(db, eng, now)

    load_model()
    sim = simulator.compare(simulator.SimParams())
    db.add(ScenarioRun(kind="policy_comparison", seed=sim["params"]["seed"], params=sim["params"], result=sim,
                       result_hash=sim["result_hash"]))
    audit(db, "system", "seed", "database", "demo",
          {"note": "Synthetic demo fleet seeded; sensor streams replay NASA C-MAPSS FD001 hold-out engines.",
           "fingerprint": hashlib.sha256(json.dumps(TARGET_REMAINING).encode()).hexdigest()[:12]})
    db.commit()
    log.info("seed: synthetic demo fleet created")


if __name__ == "__main__":
    with SessionLocal() as s:
        seed(s)
