# PROGRESS

_Last updated: 2026-10-20 (session 1)_

## Completed (verified by running)
- Repo cloned (was empty); dataset downloaded from NASA S3, sha256 `c9c5dec1…ad3b2`, FD001 schema verified (26 cols).
- ML: `python -m ml.train` trains in ~14 s. Test RMSE 15.74 / MAE 11.51 (Ridge 21.47 / 17.04, mean 41.7 CV);
  90% conformal coverage 0.89 on test (capped truth), 0.90 on 20 hold-out engines. SHAP == pred_contrib (diff 0.0).
- Backend services: TrustTwin gate, recommendations, CP-SAT planner + greedy baseline + verifier, scenario engine,
  policy simulator (deterministic hash per seed), ingestion adapters (4 sources), audit hash chain, RBAC, copilot (off).
- API routers: auth, fleet, maintenance (work orders, decisions, schedules, technicians, records), parts, trusttwin,
  simulation, ingestion, reports (CSV), system (health, status, model, drift, thresholds, users, copilot).
- Alembic initial migration; seed; smoke-tested on SQLite **and PostgreSQL 16** (Neon-style URL normalisation).
- Neon PostgreSQL adopted as primary hosted DB (owner directive); Supabase references removed (MASTER_PROMPT §26).

## Active
- Automated tests (pytest) for the 18 mandatory scenarios.

## Pending
- Frontend (9 pages), Vitest, Playwright/e2e smoke, Docker Compose + Dockerfiles, docs/ folder, README,
  THIRD_PARTY_NOTICES.md, sample ingestion files (`data/samples/`), ponytail review, commit + push.
- Connect to the owner's Neon instance once `DATABASE_URL` is provided in `.env` (never committed).

## Known issues / blockers
- Neon not yet connected: needs the owner's connection string.

## Next steps
1. Write `backend/tests` + `ml/tests`, run pytest.
2. Build frontend; wire to API; build + Vitest.
3. Docker Compose (postgres + backend + nginx frontend); verify startup.
4. Docs, README; commit with owner's git identity (no AI attribution); push.
