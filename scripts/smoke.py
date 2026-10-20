"""End-to-end smoke test against a running stack (through the frontend's /api proxy).

    python scripts/smoke.py [BASE_URL]        # default http://localhost:8080 (Docker); dev: http://localhost:5173
Requires DEMO_PASSWORD in the environment or .env. Exits non-zero on the first failed step.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
if not BASE.startswith(("http://", "https://")):
    sys.exit("BASE_URL must be http(s)")
PW = os.environ.get("DEMO_PASSWORD") or next(
    (ln.split("=", 1)[1].strip() for ln in (Path(__file__).parents[1] / ".env").read_text().splitlines()
     if ln.startswith("DEMO_PASSWORD=")), "")


def call(method, path, body=None, token=None, expect=200):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,  # noqa: S310
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
            status, data = r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        status, data = e.code, json.loads(e.read() or b"null")
    assert status == expect, f"{method} {path}: {status} {data}"
    return data


def step(name, fn):
    out = fn()
    print(f"ok  {name}")
    return out


html = urllib.request.urlopen(BASE + "/", timeout=30).read().decode()  # noqa: S310
assert '<div id="root">' in html
print("ok  SPA served")
step("health", lambda: call("GET", "/api/health")["status"] == "ok" or sys.exit("health degraded"))
tok = step("login officer", lambda: call("POST", "/api/auth/login", {"username": "officer", "password": PW})["access_token"])
ana = step("login analyst", lambda: call("POST", "/api/auth/login", {"username": "analyst", "password": PW})["access_token"])
fleet = step("fleet", lambda: call("GET", "/api/aircraft", token=tok))
eng = next(e for a in fleet["items"] for e in a["engines"] if e["serial"] == "AP-ENG-01")
base = step("baseline scenario", lambda: call("POST", "/api/trusttwin/scenarios", {"engine_id": eng["id"]}, tok, 201))
assert base["result"]["baseline"]["assessment"]["state"] == "VALID"
run = step("disrupted scenario", lambda: call("POST", "/api/trusttwin/scenarios", {
    "engine_id": eng["id"], "unavailable_parts": ["APX-HPT-MOD-KIT"], "part_delay_days": 10,
    "dropout_sensors": ["s4", "s11"], "dropout_last_n": 2}, tok, 201))
assert run["result"]["revised"]["assessment"]["state"] == "DEGRADED", run["result"]["revised"]["assessment"]["state"]
sched = run["review"]["schedules"][1]["id"]
step("analyst cannot approve (403)", lambda: call("POST", "/api/decisions", {"target_type": "schedule", "target_id": sched,
                                                                              "decision": "approve"}, ana, 403))
step("officer approves revised plan", lambda: call("POST", "/api/decisions", {"target_type": "schedule", "target_id": sched,
                                                                               "decision": "approve", "reason": "smoke"}, tok, 201))
step("live CP-SAT plan", lambda: call("POST", "/api/schedules", {"solver": "cp-sat"}, tok, 201)["solver_status"] in ("OPTIMAL", "FEASIBLE")
     or sys.exit("planner failed"))
step("audit chain valid", lambda: call("GET", "/api/audit/verify", token=tok)["valid"] or sys.exit("audit chain broken"))
print("SMOKE PASSED")
