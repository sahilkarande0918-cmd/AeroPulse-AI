# PROJECT_CONTEXT — AeroPulse AI

**What:** advisory, explainable predictive-maintenance & fleet-availability decision support platform.
**Problem:** SIH26249 "Air Power – Predictive Maintenance & Fleet Availability" (MoD India / DSSC): fragmented,
reactive maintenance data → late fault prediction, avoidable downtime. Full requirements: [MASTER_PROMPT.md](MASTER_PROMPT.md).

**Never claimed:** validation on military aircraft, airworthiness/dispatch authority, certification. Data = public
NASA C-MAPSS (simulated commercial turbofans) + clearly labelled synthetic fleet/records.

## Architecture (modular monolith)

```
CSV/JSON adapters ─► PostgreSQL (Neon hosted | local Docker) ◄─ FastAPI routers (RBAC, audit)
                                   │
 ml/ (features, train, inference) ─┼─► services/trust.py   TrustTwin data-quality gate + conformal RUL
                                   ├─► services/fleet.py   predictions → recommendations → work orders
                                   ├─► services/planner.py OR-Tools CP-SAT + greedy baseline + verifier
                                   ├─► services/trusttwin.py what-if scenarios (sandboxed)
                                   └─► services/simulator.py reactive vs predictive digital twin
React SPA (frontend/) ──► /api/*
```

| Area | Location |
|---|---|
| Dataset download/parse (sha256-verified) | `ml/data.py` |
| Causal features (shared train/inference) | `ml/features.py` |
| Training, CV, conformal, SHAP, plots | `ml/train.py` → `ml/artifacts/`, `ml/evaluation/` |
| Inference + intervals + TreeSHAP | `ml/inference.py` |
| DB models (Prediction / Recommendation / Decision separate) | `backend/app/models.py` |
| Auth, roles, audit hash chain | `backend/app/security.py` |
| Ingestion + versioned mapping | `backend/app/services/ingestion.py`, `backend/app/mappings/mapping_v1.json` |
| Seed (synthetic fleet replaying C-MAPSS hold-out engines) | `backend/app/seed.py` |

## Model
LightGBM regressor, FD001, target RUL capped at 125. Engine split 65 fit / 15 calibration / 20 hold-out; model
selection by 5-fold GroupKFold. Mondrian split-conformal 90% intervals (bins on predicted RUL).
Measured (official test set, 100 engines): RMSE 15.74, MAE 11.51 vs Ridge 21.47 / 17.04; coverage 0.89 (capped truth).
Version string: `fd001-lgbm_a-e2bd89e2`. Full numbers: `ml/artifacts/evaluation_report.json`.

## TrustTwin (flagship)
Checks: missing fields, invalid/implausible values (+Kelvin hint), units, step deviation, staleness, history length,
training-distribution (OOD). States VALID / DEGRADED / UNAVAILABLE; UNAVAILABLE never yields an RUL. Thresholds are
prototype settings (`DEFAULT_TRUST_THRESHOLDS`, admin-editable). Scenarios perturb data (advance real degradation,
dropout, bias, noise, staleness) and resources (parts, technicians, extra inspections), re-plan with CP-SAT, diff
baseline vs revised, compute engine risk margins, and route the result to human review. Scenarios never mutate live data.

## Database
Primary hosted: **Neon PostgreSQL** via SQLAlchemy 2 + Alembic (psycopg 3, `sslmode=require`, pooler-safe settings).
Verified live on Neon (us-east-2) on 2026-10-21. Offline/on-prem: local PostgreSQL container. SQLite only for
tests/quick dev. No Supabase.
