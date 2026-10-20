# Deployment

## Options

| Mode | Database | Command | Internet at runtime |
|---|---|---|---|
| Local development | SQLite file (`backend/aeropulse_dev.db`) or any PostgreSQL | `python manage.py migrate && python manage.py seed && python manage.py serve` + `npm --prefix frontend run dev` | No |
| Offline / on-premise / **live demos** | PostgreSQL 16 container | `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build` | **No** |
| Hosted demo | **Neon PostgreSQL** | set `DATABASE_URL` in `.env`, `docker compose up -d --build` | Yes (to Neon only) |

The same Alembic migrations run on all three. Nothing in the core platform calls an external service; the optional
LLM explainer is the only outbound call and is disabled unless `LLM_ENABLED=true` and `GEMINI_API_KEY` are set.
FastAPI's built-in OpenTelemetry hooks export nothing unless an OTLP exporter is configured (none is).

## Required configuration (`.env`, never committed)

```
JWT_SECRET_KEY=<python -c "import secrets;print(secrets.token_urlsafe(48))">
DEMO_PASSWORD=<password for the 4 seeded demo users>
POSTGRES_PASSWORD=<only for docker-compose.local.yml>
DATABASE_URL=<only for Neon>
```

The backend container runs with `APP_ENV=production` and refuses to start without `JWT_SECRET_KEY`.

## Neon PostgreSQL

1. Create a Neon project and database (e.g. `aeropulse`); copy the connection string from *Connection details*.
2. Put it in `.env` as `DATABASE_URL=postgresql://USER:PASSWORD@ep-…neon.tech/aeropulse?sslmode=require`.
   `postgres://` and `postgresql://` are both accepted and routed through psycopg 3.
3. `docker compose up -d --build` (base file only) — or locally `python manage.py migrate && python manage.py seed`.

**Verified 2026-10-21** against the project's Neon database (PostgreSQL 18.6, AWS us-east-2, pooled endpoint with
`sslmode=require&channel_binding=require`; client TLS confirmed): migration and seed succeed and are idempotent on re-run,
seeded contents match local runs (20 predictions: 16 VALID / 4 DEGRADED), `scripts/smoke.py` passes both for the local
dev server and for the Docker stack using Neon, the audit chain verifies, and data survives a backend restart.

**Latency: put the backend next to the database.** Each query to us-east-2 from India costs ~280 ms, so a page that
needs 8–18 queries takes 2–6 s (relationships are batch-loaded with `lazy="selectin"`, so the query count no longer grows
with fleet size). For demos, either use the local database (below), host the backend in the same region as Neon, or create the
Neon project in the region nearest to where the backend runs.

Engine settings tuned for Neon (`backend/app/database.py`): `pool_pre_ping` + `pool_recycle=300` survive compute
auto-suspend; `prepare_threshold=None` keeps the PgBouncer pooler endpoint (`-pooler` host, transaction mode) safe;
TLS is enforced by `sslmode=require` in the URL. Only non-sensitive demonstration data should go to a hosted service.

## Free-tier hosting

| Piece | Service (free plan) | Config |
|---|---|---|
| Frontend (static SPA) | Vercel | `frontend/vercel.json` — builds Vite, rewrites `/api/*` to Render (same origin for the browser), CSP + security headers |
| Backend (FastAPI, Docker) | Render Free web service, region Ohio | `render.yaml` — `plan: free`, `healthCheckPath: /health`, secrets entered in Render |
| Database | Neon Free, AWS us-east-2 | pooled connection string with `sslmode=require` |
| Uptime | UptimeRobot Free, 5-minute HTTP check | `GET https://<render-service>.onrender.com/health` |

Render Free sleeps after 15 minutes without traffic; the 5-minute monitor keeps it awake (one service ≈ 730 h/month,
inside the 750 free instance-hours). `/health` deliberately touches neither the database nor the model, so the pings do
not keep the Neon compute awake. Paid plans are never enabled without the owner's approval.

### Measured on Render-equivalent limits (Docker `--cpus 0.1 --memory 512m`, final image, 2026-10-21)

| Metric | Value |
|---|---|
| Image (Python 3.11-slim + LightGBM, OR-Tools, pandas, SciPy; no scikit-learn/SHAP/matplotlib) | 878 MB on disk |
| Memory after startup / peak incl. 365-day × 40-aircraft stress simulation | 127 MiB / 154 MiB (limit 512) |
| Cold start (migrate + seed check + model + hold-out predictions) to serving | 39 s (was 90 s with three processes) |
| Page data (fleet, overview, parts, work orders, model) | 0.1–0.3 s |
| TrustTwin disrupted scenario (3 plans + 2 assessments) first / repeated | 1.6–2.0 s / ~1.0 s |
| CP-SAT plan, live backlog | 0.2–0.6 s |
| Login (bcrypt cost 12, intentionally slow) | ~3 s |
| Playwright suite (4 browser tests) + `scripts/smoke.py` | pass |

Optimisations that got there, all result-preserving and tested: native LightGBM Booster artifact (no scikit-learn at
runtime), inference features computed on the last 20 readings only, CP-SAT plans cached by input hash with a
deterministic-time limit, OpenMP pinned to one thread, model + hold-out predictions warmed at startup, and one Python
process for migrate + seed + serve (`python manage.py start`). Training never runs on Render (`ml/` training extras are
not installed in the image).

## Local PostgreSQL (offline / on-prem / live demos)

`docker-compose.local.yml` adds the database and **overrides** `DATABASE_URL`, so this mode stays local even when `.env`
holds a Neon URL. Measured on the demo laptop (2026-10-21): every page's API data in 7–39 ms, pages rendered in the
browser in 12–260 ms, a disrupted TrustTwin scenario from click to results in 335 ms, policy comparison in ~70 ms. The
API warms the model and hold-out predictions at startup, so the first click is as fast as the rest.


`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build` starts `db` (postgres:16-alpine, volume `pgdata`), `backend`
(migrates, seeds once, serves on the internal network) and `frontend` (nginx on http://localhost:8080 serving the built
SPA and proxying `/api`). Fonts, scripts and the model are all inside the images.

Verified on this machine: migrations + seed + TrustTwin scenario + audit-chain verification on PostgreSQL 16 with a
Neon-style `postgresql://` URL.

## Migrations

```
python manage.py migrate                     # upgrade to head
cd backend && alembic revision --autogenerate -m "describe change"   # after editing app/models.py
```

The container runs `alembic upgrade head` on every start (idempotent).

## Backup and recovery

* Local PostgreSQL: `docker compose exec db pg_dump -U aeropulse -Fc aeropulse > aeropulse_$(date +%F).dump`;
  restore with `pg_restore -U aeropulse -d aeropulse --clean`. Schedule daily dumps and keep them off-host.
* Neon: point-in-time restore / branching from the Neon console, plus periodic `pg_dump` for an independent copy.
* Model artifacts are versioned in git; `python manage.py train` regenerates them bit-for-bit from the NASA archive.
* Audit integrity after restore: `GET /api/audit/verify`.

## Storage locations

| Data | Location |
|---|---|
| Operational records, predictions, decisions, audit | PostgreSQL |
| Model + evaluation artifacts | `ml/artifacts/` (in the backend image) |
| Raw NASA download (training only) | `ml/data/raw/` (git-ignored, not in images) |
| Uploaded import files | Not stored — parsed in memory; only validated records and a batch report are kept |

## Installation requirements

Docker 24+ with Compose v2.20+ (for optional `depends_on`), or Python 3.11 + Node 20 for development. ~1.5 GB disk for
images. No GPU.
