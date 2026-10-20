# Architecture

AeroPulse AI is a **modular monolith**: one FastAPI process, one PostgreSQL database, one static React bundle.
Module boundaries are explicit so a later split is possible, but nothing requires it today.

| Module | Code | Responsibility |
|---|---|---|
| Data ingestion | `backend/app/services/ingestion.py`, `backend/app/mappings/mapping_v1.json` | Adapters for 4 source types, validation, provenance |
| Prediction & explanation | `ml/features.py`, `ml/inference.py` | Causal features, LightGBM RUL, conformal interval, TreeSHAP |
| Trust assessment | `backend/app/services/trust.py` | Data-quality checks and VALID / DEGRADED / UNAVAILABLE gate |
| Recommendations & glue | `backend/app/services/fleet.py` | Prediction → recommendation → work order; builds planning problems |
| Maintenance scheduling | `backend/app/services/planner.py` | CP-SAT optimiser, greedy baseline, independent constraint verifier |
| What-if & simulation | `backend/app/services/trusttwin.py`, `backend/app/services/simulator.py` | Sandboxed scenarios; reactive vs predictive digital twin |
| Persistence & audit | `backend/app/models.py`, `backend/app/security.py`, `backend/alembic/` | SQLAlchemy models, migrations, RBAC, hash-chained audit |
| Web presentation | `backend/app/api/*`, `frontend/src/*` | REST API (OpenAPI at `/docs`) and the React console |

## 1. Overall system

```mermaid
flowchart TB
  browser[Browser - React console] -->|HTTPS /api| nginx[nginx: static assets + reverse proxy]
  nginx --> api[FastAPI app\nRBAC · validation · error schema]
  api --> svc[Services\ntrust · fleet · planner · trusttwin · simulator · ingestion]
  svc --> mdl[ml/ inference\nrul_model.joblib]
  svc --> db[(PostgreSQL\nNeon or self-hosted)]
  api -. optional, off by default .-> llm[Gemini explainer]
```

## 2. ML training and inference pipeline

```mermaid
flowchart LR
  zip[NASA archive\nsha256 verified] --> parse[parse train/test/RUL\nschema checks]
  parse --> split[split by engine\n65 fit · 15 calib · 20 hold-out]
  split --> sel[sensor selection\non fit engines only]
  sel --> feat[causal rolling features\nmean/std 10 · slope 20]
  feat --> cv[GroupKFold CV\nmean · ridge · 2 LightGBM]
  cv --> fit[refit best on fit engines]
  fit --> conf[Mondrian conformal\non calibration engines]
  conf --> eval[test_FD001 + hold-out evaluation\nSHAP check · plots · report]
  eval --> art[(artifacts:\nmodel · schema · report)]
  art --> inf[runtime: same build_features\n→ predict → interval → pred_contrib]
```

## 3. TrustTwin decision flow

```mermaid
flowchart TB
  r[latest readings of one engine] --> c1{missing / invalid /\nunits / spike / stale /\nhistory}
  c1 -->|any fail| U[UNAVAILABLE\nno RUL produced]
  c1 -->|warn only| imp[impute by carrying last value forward]
  c1 -->|pass| f[features]
  imp --> f
  f --> ood{share of features outside\ntraining p0.5–p99.5}
  ood -->|> 0.6| U
  ood -->|> 0.25| D[DEGRADED\nRUL + interval, flagged]
  ood -->|ok, no warnings| V[VALID\nRUL + interval]
  ood -->|ok, earlier warnings| D
  V --> rule[prototype recommendation rules\nlower bound ≤ 15 → replacement · ≤ 40 → inspection]
  D --> ver[verify sensors · inspect if bound low]
  U --> ver
  rule --> rec[Recommendation - proposed]
  ver --> rec
  rec --> off{Officer: approve · reject ·\nrequest inspection · request data}
```

## 4. Maintenance optimisation workflow

```mermaid
flowchart LR
  wo[open + pending work orders] --> prob[Problem builder\nhours from horizon start]
  tech[technicians: skills, IST shifts, leave] --> prob
  parts[parts: on hand + replenishment] --> prob
  prob --> diag[static diagnosis\nno skill · no window · no parts · blocked predecessor]
  diag --> cps[CP-SAT\noptional intervals · NoOverlap per tech & aircraft\nreservoir for parts · precedence]
  prob --> gr[greedy EDD baseline]
  cps --> ver[verify all hard constraints]
  gr --> ver
  ver --> exp[per-task explanation + KPIs]
  exp --> ok{officer approves?}
  ok -->|yes| apply[work orders scheduled with tech + start]
```

Objective (weights configurable per request): Σ priority_weight × (lateness_w × hours late + unscheduled_w ×
[unscheduled] + completion_w × finish hour), priority weights P1..P4 = 8, 4, 2, 1. Solver runs single-worker with a
fixed seed so identical inputs give identical plans. Each plan stores the SHA-256 of its input problem.

## 5. Data integration architecture

```mermaid
flowchart LR
  f[CSV / JSON file\n≤ 5 MB, never stored on disk] --> h{same file hash\nalready imported?}
  h -->|yes| prev[return previous batch report]
  h -->|no| map[mapping-v1: column aliases,\nunits + conversions, enums]
  map -->|missing columns / bad unit| schema[batch rejected: schema error]
  map --> rows[row validation\ntimestamps → UTC]
  rows -->|invalid| rej[rejected rows report]
  rows --> key{natural key exists?}
  key -->|identical| dup[duplicate - skipped]
  key -->|different| conf[conflict - NOT merged]
  key -->|new| ins[insert with batch_id + source id]
  ins --> refresh[sensor data → refresh predictions]
```

## Key data entities

`Aircraft`, `Engine` (with C-MAPSS source unit), `SensorReading` (JSON values; missing keys = missing data),
`Prediction` (state, RUL, interval, checks, evidence, model version), `Recommendation`, `Decision`, `WorkOrder`,
`Technician`, `Part`, `MaintenanceRecord`, `Schedule` (stored result + input hash), `ScenarioRun` (params, result,
result hash), `IngestionBatch`, `AuditEvent` (prev_hash, hash), `AppSetting` (trust thresholds).
