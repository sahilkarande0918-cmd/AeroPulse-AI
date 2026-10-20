# PROGRESS

_Last updated: 2026-10-21 (session 1)_

## Completed (verified by running)
- **Repo**: cloned (was empty); commits under the owner's git identity, no AI attribution.
- **Dataset**: NASA S3 archive, sha256 `c9c5dec1…ad3b2`, FD001 schema verified.
- **ML** (`python manage.py train`, ~20 s): LightGBM selected by engine-grouped CV (14.91 vs Ridge 20.73).
  Official test: RMSE 15.74 / MAE 11.51 (Ridge 21.47 / 17.04). Conformal 90 %: 0.89 test, 0.899 hold-out.
  SHAP == pred_contrib. Artifacts + plots committed.
- **Backend**: TrustTwin gate, recommendations, CP-SAT planner + greedy baseline + verifier, sandboxed scenarios,
  policy simulator, 4 ingestion adapters, RBAC, audit hash chain, CSV reports, drift summary, thresholds, users,
  optional Gemini explainer (off). Alembic migration. `manage.py migrate|seed|serve|train`.
- **Database**: Neon PostgreSQL is the primary hosted target (owner directive, MASTER_PROMPT §26); verified on
  PostgreSQL 16 with a Neon-style `postgresql://` URL. Local Docker PostgreSQL for offline. No Supabase anywhere.
- **Frontend**: 9 pages wired to the live API; verified in browser at 1440 px and 375 px (no horizontal overflow on any
  page, no console errors); TrustTwin demo flow exercised end-to-end in the UI.
- **Docs**: README, docs/{architecture, model-training, evaluation, deployment, integration-guide, security,
  limitations, demo-guide}.md, THIRD_PARTY_NOTICES.md.
- **Ponytail audit** run; cuts applied (audit body dedupe, sensor list from API, unused dep, dead wrapper/param).

## Last verified test results
- `pytest`: **65 passed** · `ruff check .`: clean
- `npm test` (Vitest): **8 passed** · `npm run build`: OK · `check:secrets`: OK (and proven to catch a planted secret)
- `npm run lint`: 0 errors (6 fast-refresh warnings, dev-only)

- **Docker** (`docker compose --profile local-db up -d --build`): db + backend + frontend healthy; migrate + seed on
  start; `scripts/smoke.py http://localhost:8080` **passed**; CSP/X-Frame headers present; decisions persist across a
  backend container restart on PostgreSQL.

- **Neon connected and verified** (2026-10-21): `DATABASE_URL` in `.env` (git-ignored), PostgreSQL 18.6 in AWS
  us-east-2 via the pooled endpoint with TLS. Migrate + seed done (idempotent); smoke passes for dev server and Docker
  stack on Neon; persistence across restart and audit chain verified. N+1 lazy loading fixed (D18).
  Docker backend currently points at Neon (local `pgdata` volume kept for `--profile local-db`).

## Active / pending
- Neon now holds a few smoke-test scenario runs/decisions; reset steps in docs/demo-guide.md if a clean demo is wanted.

## Known issues / blockers
- Slow networks can make the first backend image build take a long time (Dockerfile retries pip downloads).
- Neon round trip ~280 ms from India → 2–6 s page loads; host the backend near the database for demos.

## Next steps
1. Possible improvements: FD002–FD004 multi-condition models; OIDC; rolling-horizon re-planning; Playwright suite.
