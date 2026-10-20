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

- **Docker** (`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build`): db + backend + frontend healthy; migrate + seed on
  start; `scripts/smoke.py http://localhost:8080` **passed**; CSP/X-Frame headers present; decisions persist across a
  backend container restart on PostgreSQL.

- **Neon connected and verified** (2026-10-21): `DATABASE_URL` in `.env` (git-ignored), PostgreSQL 18.6 in AWS
  us-east-2 via the pooled endpoint with TLS. Migrate + seed done (idempotent); smoke passes for dev server and Docker
  stack on Neon; persistence across restart and audit chain verified. N+1 lazy loading fixed (D18).
- **Live-demo mode** (2026-10-21): `docker-compose.local.yml` forces the bundled PostgreSQL even with a Neon URL in
  `.env`; API warm-up at startup. Measured: page data 7–39 ms, browser render 12–260 ms, TrustTwin scenario click→result
  335 ms. **Currently running** in this mode at http://localhost:8080 with a freshly seeded database.

- **Render-Free readiness** (2026-10-21): native Booster artifact (no scikit-learn at runtime), 20-reading inference
  window, CP-SAT plan cache + deterministic-time limit, OMP=1, startup warm-up, single-process `manage.py start`,
  DB-free `GET /health`. Measured at 512 MB / 0.1 CPU: 127 MiB idle, 154 MiB peak, cold start 39 s, scenario 1–2 s.
  `render.yaml` + `frontend/vercel.json` written. No Oracle configs ever existed.
- **Gaps closed**: mypy clean (`--check-untyped-defs`), pip-audit + npm audit clean (Vitest 5), ESLint 0 warnings,
  OIDC bearer mode (`AUTH_MODE=oidc`, tested), FD001–FD004 benchmark, SVG engine schematic, Copilot UI panel (hidden
  when disabled), print/PDF stylesheet, Playwright suite (4 tests, local Edge) + README screenshots.

## Last verified test results (2026-10-21)
- pytest **77 passed** · ruff clean · mypy clean (33 files)
- Vitest **11 passed** · ESLint 0 · build OK · secret scan OK · npm audit 0 · pip-audit 0
- Playwright **4 passed** + `scripts/smoke.py` passed on the production images capped at 512 MB / 0.1 CPU

- **Deployed and verified live (2026-10-21)**: Vercel https://aero-pulse-ai-kohl.vercel.app (owner-created project
  `aero-pulse-ai`, root `frontend`, auto-deploys from main) → Render Free `aeropulse-api` (srv-dbbsksfavr4c73dfp0ig,
  Ohio, https://aeropulse-api-o93e.onrender.com, auto-deploy off) → Neon (reset + re-seeded with PROD_DEMO_PASSWORD) ·
  UptimeRobot monitor 804355902, 5 min, `/health` (HEAD fixed). Live smoke + 4 Playwright tests pass.

## Active / pending
- None. Owner action before judging: Settings → Reset demo data.

## Known issues / blockers
- Slow local network makes first Docker builds slow (pip retries configured).
- Render Free: 0.1 CPU → login ~3 s (bcrypt), scenarios 1–2 s; sleeps after 15 min idle without the uptime monitor.

## Next steps
1. Possible improvements: multi-condition production model; WORM audit anchoring; real IdP integration.
