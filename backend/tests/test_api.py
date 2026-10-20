"""API integration: auth/RBAC (13), approvals + audit (12), scenarios (9), ingestion, persistence (16)."""
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.database import make_engine
from app.models import AuditEvent, Decision, Recommendation, WorkOrder
from tests.conftest import PASSWORD, auth

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def test_health_and_error_schema(client):
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/aircraft")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    r = client.post("/api/auth/login", json={"username": "admin"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_liveness_needs_no_database(client):
    from app.database import get_db
    from app.main import app

    def broken():
        raise RuntimeError("database down")
        yield
    app.dependency_overrides[get_db] = broken
    assert client.get("/health").json() == {"status": "ok"}


def test_login_rejects_bad_password_and_rate_limits(client):
    for _ in range(10):
        assert client.post("/api/auth/login", json={"username": "officer", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "officer", "password": PASSWORD}).status_code == 429


def test_fleet_and_detail(client):
    h = auth(client, "analyst")
    fleet = client.get("/api/aircraft", headers=h).json()
    assert fleet["total"] == 10
    states = {e["prediction"]["state"] for a in fleet["items"] for e in a["engines"]}
    assert "VALID" in states and "DEGRADED" in states          # AP-107 stale, AP-ENG-08 dropout, AP-ENG-19 new
    ac = client.get(f"/api/aircraft/{fleet['items'][0]['id']}", headers=h).json()
    eng = ac["engines"][0]
    assert eng["prediction"]["checks"] and eng["prediction"]["model_version"].startswith("fd001-")
    rd = client.get(f"/api/engines/{eng['id']}/readings?last=50", headers=h).json()
    assert len(rd["readings"]) == 50 and "s2" in rd["sensors"]
    assert client.get("/api/fleet/overview", headers=h).json()["simulated_availability"]["label"].startswith("Results from a simulated")


@pytest.mark.parametrize("role", ["technician", "analyst"])
def test_unauthorised_roles_cannot_approve(client, role, db):  # scenario 13
    h = auth(client, role)
    rec = db.scalar(select(Recommendation).where(Recommendation.status == "proposed"))
    r = client.post("/api/decisions", headers=h, json={"target_type": "recommendation", "target_id": rec.id, "decision": "approve"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert client.post("/api/schedules", headers=h, json={}).status_code == 403
    assert client.patch("/api/parts/APX-OIL-FILTER", headers=h, json={"on_hand": 1, "reason": "test"}).status_code == 403
    assert client.post("/api/ingestion/parts", headers=h, files={"file": ("p.csv", b"x")}).status_code == 403


def test_operator_approval_recorded(client, Session):  # scenario 12
    h = auth(client, "officer")
    recs = client.get("/api/recommendations?status=proposed", headers=h).json()["items"]
    rec = recs[0]
    bad = client.post("/api/decisions", headers=h, json={"target_type": "recommendation", "target_id": rec["id"], "decision": "reject"})
    assert bad.status_code == 422                                # reason required for rejection
    r = client.post("/api/decisions", headers=h, json={"target_type": "recommendation", "target_id": rec["id"],
                                                         "decision": "approve", "reason": "Evidence reviewed"})
    assert r.status_code == 201 and r.json()["user"] == "officer" and r.json()["effect"]["work_order"]
    again = client.post("/api/decisions", headers=h, json={"target_type": "recommendation", "target_id": rec["id"], "decision": "approve"})
    assert again.status_code == 409
    with Session() as s:
        d = s.scalar(select(Decision).where(Decision.target_id == rec["id"]))
        assert d.decision == "approve" and d.user.username == "officer"
        wo = s.scalar(select(WorkOrder).where(WorkOrder.code == r.json()["effect"]["work_order"]))
        assert wo.approval_state == "approved" and wo.source == "recommendation"
        assert s.scalar(select(AuditEvent).where(AuditEvent.action == "decision.approve")) is not None
    assert client.get("/api/audit/verify", headers=h).json()["valid"] is True


def test_schedule_propose_approve_applies_to_work_orders(client, db):
    h = auth(client, "officer")
    s = client.post("/api/schedules", headers=h, json={"solver": "cp-sat"}).json()
    assert s["solver_status"] in ("OPTIMAL", "FEASIBLE") and s["kpis"]["scheduled"] > 0
    g = client.post("/api/schedules", headers=h, json={"solver": "greedy"}).json()
    assert g["objective"] >= s["objective"]
    assert client.get(f"/api/schedules/{s['id']}", headers=h).json()["status"] == "superseded"
    r = client.post("/api/decisions", headers=h, json={"target_type": "schedule", "target_id": g["id"], "decision": "approve"})
    assert r.status_code == 201 and r.json()["effect"]["work_orders_scheduled"] == g["kpis"]["scheduled"]
    scheduled = client.get("/api/work-orders?status=scheduled", headers=h).json()
    assert scheduled["total"] == g["kpis"]["scheduled"] and all(w["assigned_technician"] for w in scheduled["items"])


def test_inventory_change_influences_planning(client):  # acceptance: inventory disruption changes planning
    h = auth(client, "officer")
    before = client.post("/api/schedules", headers=h, json={}).json()
    wo2 = next(a for a in before["assignments"] if a["task"] == "WO-0002")    # needs APX-T50-PROBE (arrives later)
    r = client.patch("/api/parts/APX-T50-PROBE", headers=h, json={"on_hand": 2, "reason": "Emergency stock transfer"})
    assert r.status_code == 200 and r.json()["on_hand"] == 2
    after = client.post("/api/schedules", headers=h, json={}).json()
    wo2_after = next(a for a in after["assignments"] if a["task"] == "WO-0002")
    assert wo2_after["start"] < wo2["start"]
    client.patch("/api/parts/APX-T50-PROBE", headers=h, json={"on_hand": 0, "clear_replenishment": True, "reason": "Recall"})
    gone = client.post("/api/schedules", headers=h, json={}).json()
    assert any(u["task"] == "WO-0002" and "APX-T50-PROBE" in u["reason"] for u in gone["unscheduled"])


def test_trusttwin_scenario_end_to_end(client):  # demo flow: degradation -> part out -> dropout -> review
    h = auth(client, "officer")
    eng = next(e for a in client.get("/api/aircraft", headers=h).json()["items"] for e in a["engines"] if e["serial"] == "AP-ENG-01")
    base = client.post("/api/trusttwin/scenarios", headers=h, json={"engine_id": eng["id"]}).json()
    assert base["result"]["baseline"]["assessment"]["state"] == "VALID"
    assert base["result"]["baseline"]["recommendation"]["task_type"] == "replacement"
    task = f"TT-E{eng['id']}"
    b_start = next(a["start"] for a in base["result"]["revised"]["plan"]["assignments"] if a["task"] == task)
    part = client.post("/api/trusttwin/scenarios", headers=h, json={"engine_id": eng["id"], "unavailable_parts": ["APX-HPT-MOD-KIT"]}).json()
    moved = next(a for a in part["result"]["revised"]["plan"]["assignments"] if a["task"] == task)
    assert moved["start"] > b_start and "APX-HPT-MOD-KIT" in moved["explanation"]   # waits for replenishment
    slip = client.post("/api/trusttwin/scenarios", headers=h, json={"engine_id": eng["id"], "unavailable_parts": ["APX-HPT-MOD-KIT"],
                                                                     "part_delay_days": 20}).json()
    unsched = {u["task"]: u["reason"] for u in slip["result"]["revised"]["plan"]["unscheduled"]}
    assert "APX-HPT-MOD-KIT" in unsched[task]                                          # scenario 9 via API
    assert any(r["flag"] == "unscheduled" for r in slip["result"]["revised"]["outcomes"]["engine_risk"])
    drop = client.post("/api/trusttwin/scenarios", headers=h, json={
        "engine_id": eng["id"], "dropout_sensors": ["s2", "s3", "s4"], "unavailable_parts": ["APX-HPT-MOD-KIT"],
        "unavailable_technicians": ["TECH-01"]}).json()
    rev = drop["result"]["revised"]
    assert rev["assessment"]["state"] == "UNAVAILABLE" and rev["assessment"]["rul"] is None
    assert rev["recommendation"]["task_type"] == "troubleshooting"
    assert all(a["technician"] != "TECH-01" for a in rev["plan"]["assignments"])
    sched_id = drop["review"]["schedules"][1]["id"]
    d = client.post("/api/decisions", headers=h, json={"target_type": "schedule", "target_id": sched_id, "decision": "approve",
                                                        "reason": "Verification first"}).json()
    assert d["effect"]["live"] is False
    detail = client.get(f"/api/trusttwin/scenarios/{drop['id']}", headers=h).json()
    assert detail["review"]["decisions"][0]["user"] == "officer"
    assert client.post("/api/trusttwin/scenarios", headers=h, json={"engine_id": eng["id"], "dropout_sensors": ["bogus"]}).status_code == 422


def test_scenario_reproducible(db):
    from datetime import UTC, datetime

    from app.services import trusttwin
    now = datetime(2026, 10, 20, 6, 30, tzinfo=UTC)
    p = trusttwin.ScenarioParams(engine_id=3, noise_sigma=2, seed=5, unavailable_parts=["APX-BORESCOPE-SEAL"])
    a, b = trusttwin.run(db, p, None, now=now), trusttwin.run(db, p, None, now=now)
    assert a.result_hash == b.result_hash


def test_ingestion_samples(client):
    h = auth(client, "officer")

    def up(source, name, src="EXT-CAMO"):
        return client.post(f"/api/ingestion/{source}", headers=h, data={"source_name": src},
                           files={"file": (name, (SAMPLES / name).read_bytes())}).json()
    s = up("sensor", "sensor_readings.csv")
    assert (s["accepted"], s["duplicates"], s["conflicts"], s["rejected"]) == (4, 1, 1, 2)
    assert up("sensor", "sensor_readings.csv")["already_imported"] is True                 # idempotent file
    k = up("sensor", "sensor_readings_kelvin.csv")
    assert k["accepted"] == 1 and any("K -> degR" in n for n in k["report"]["notes"])
    m = up("maintenance", "maintenance_records.csv")
    assert (m["accepted"], m["duplicates"], m["rejected"]) == (2, 1, 3)
    p = up("parts", "parts_inventory.csv")
    assert (p["accepted"], p["updated"], p["duplicates"], p["conflicts"], p["rejected"]) == (1, 1, 1, 1, 1)
    w = up("work_orders", "work_orders.json")
    assert (w["accepted"], w["rejected"]) == (2, 1)
    wos = client.get("/api/work-orders?approval_state=pending", headers=h).json()["items"]
    ext = {x["external_id"]: x for x in wos if x["source"] == "EXT-CAMO"}
    assert ext["EXT-WO-502"]["predecessors"] == [ext["EXT-WO-501"]["code"]]
    bad = client.post("/api/ingestion/sensor", headers=h, files={"file": ("x.csv", b"foo,bar\n1,2\n")}).json()
    assert bad["report"]["schema_errors"]
    assert client.post("/api/ingestion/sensor", headers=h, files={"file": ("x.exe", b"MZ")}).status_code == 422


def test_audit_tamper_detected(client, Session):
    h = auth(client, "admin")
    with Session() as s:
        s.execute(text("UPDATE audit_events SET actor='mallory' WHERE id=1"))
        s.commit()
    assert client.get("/api/audit/verify", headers=h).json()["valid"] is False


def test_data_persists_across_restart(client, db_url):  # scenario 16
    h = auth(client, "officer")
    rec = client.get("/api/recommendations?status=proposed", headers=h).json()["items"][0]
    client.post("/api/decisions", headers=h, json={"target_type": "recommendation", "target_id": rec["id"],
                                                     "decision": "request_data", "reason": "Need fresh download"})
    fresh = make_engine(db_url)                      # new engine = new process-equivalent connection pool
    with sessionmaker(bind=fresh)() as s:
        assert s.get(Recommendation, rec["id"]).status == "info_requested"
        assert s.scalar(select(Decision).where(Decision.target_id == rec["id"])).reason == "Need fresh download"
    fresh.dispose()


def test_admin_only_settings(client):
    h_off, h_adm = auth(client, "officer"), auth(client, "admin")
    body = {"thresholds": {"stale_degraded_hours": 24}, "reason": "Tighter freshness"}
    assert client.put("/api/settings/thresholds", headers=h_off, json=body).status_code == 403
    assert client.put("/api/settings/thresholds", headers=h_adm, json=body).json()["thresholds"]["stale_degraded_hours"] == 24
    assert client.get("/api/users", headers=h_off).status_code == 403
    assert client.post("/api/copilot/explain", headers=h_adm, json={"question": "why?", "prediction_id": 1}).status_code == 503


def test_reports_csv(client):
    h = auth(client, "analyst")
    r = client.get("/api/reports/recommendations.csv", headers=h)
    assert r.status_code == 200 and r.text.startswith("recommendation_id,")
    assert client.get("/api/reports/audit.csv", headers=auth(client, "technician")).status_code == 403


def test_alembic_migration_matches_models(tmp_path):
    from alembic import command
    from alembic.config import Config

    from app.database import Base
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    eng = make_engine(url)
    with eng.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    eng.dispose()
    assert set(Base.metadata.tables) <= tables


def test_demo_reset_is_admin_only_and_flag_gated(client, Session, monkeypatch):
    from app.config import settings
    h_adm, h_off = auth(client, "admin"), auth(client, "officer")
    assert client.post("/api/admin/reset-demo", headers=h_adm).status_code == 403          # flag off by default
    monkeypatch.setattr(settings, "demo_reset_enabled", True)
    assert client.post("/api/admin/reset-demo", headers=h_off).status_code == 403          # officers cannot
    rec = client.get("/api/recommendations?status=proposed", headers=h_off).json()["items"][0]
    client.post("/api/decisions", headers=h_off, json={"target_type": "recommendation", "target_id": rec["id"],
                                                         "decision": "reject", "reason": "test residue"})
    import app.api.system as system_api
    monkeypatch.setattr(system_api, "SessionLocal", Session)                                  # background task uses the test DB
    r = client.post("/api/admin/reset-demo", headers=h_adm)
    assert r.status_code == 202
    with Session() as s:
        assert s.scalar(select(Decision).limit(1)) is None
        assert s.scalar(select(AuditEvent).where(AuditEvent.action == "demo.reset")) is not None
        assert s.scalar(text("select count(*) from predictions")) == 20
