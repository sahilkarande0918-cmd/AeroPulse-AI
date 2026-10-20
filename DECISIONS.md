# DECISIONS

| # | Decision | Why |
|---|---|---|
| D1 | Modular monolith (FastAPI) not microservices | One team, one deployable; clean module boundaries are enough. |
| D2 | LightGBM on causal rolling features (mean/std/slope) | Best engine-grouped CV RMSE (14.91 vs Ridge 20.73); CPU-only, fast, TreeSHAP-native. No sequence model: no demonstrated need yet. |
| D3 | RUL target capped at 125 cycles | Standard piecewise-linear convention for C-MAPSS; early-life RUL is not identifiable from sensors. |
| D4 | Engine split 65/15/20 + GroupKFold | No engine ever appears in two splits; calibration and hold-out never seen by the fit. |
| D5 | Mondrian split-conformal intervals | Distribution-free, interpretable, measurable coverage; bins on predicted RUL give tighter intervals near end of life. Caveat: rows within an engine are correlated (exchangeability approximate); coverage is therefore reported on unseen engines. |
| D6 | Runtime explanations via LightGBM `pred_contrib` | Exact TreeSHAP (verified max diff 0.0 vs `shap.TreeExplainer`), avoids shipping `shap`/numba in the backend image. |
| D7 | Trust gate before the model; UNAVAILABLE returns no RUL | Requirement: never turn unreliable data into confident output. |
| D8 | OR-Tools CP-SAT with optional tasks + reservoir constraint for parts | Infeasible tasks become *unscheduled with a diagnosed reason* instead of a failed solve; reservoir models stock + arrivals exactly. Single worker + fixed seed for reproducibility. |
| D9 | Independent `verify()` runs on every plan | A plan violating a hard constraint raises instead of being shown. |
| D10 | Prediction / Recommendation / Decision / WorkOrder as separate tables | Human-in-the-loop accountability; the model never approves anything. |
| D11 | Audit log append-only + SHA-256 hash chain | Tamper-evident (detects edits). Not tamper-proof: a DBA can rewrite the chain. Stated as such. |
| D12 | Synthetic fleet replays C-MAPSS hold-out engines | Real sensor data and real model inference in the demo, with "future" cycles available for what-if degradation. |
| D13 | Simulator results reported as computed, not tuned | Default run: predictive policy removes unscheduled failures but does not raise availability (early replacements consume spares). Reported honestly. |
| D14 | **Neon PostgreSQL** as primary hosted DB (owner directive 2026-10-20); **no Supabase** | Plain PostgreSQL via SQLAlchemy/Alembic keeps zero provider lock-in; the same migrations run on a local Docker PostgreSQL for offline/on-prem deployment. Engine uses `pool_pre_ping`, `pool_recycle=300` (Neon autosuspend) and `prepare_threshold=None` (Neon PgBouncer pooler). |
| D15 | Local auth (bcrypt + JWT) with role checks in a single `require()` dependency | Demo-ready; OIDC/SSO replaces only the login endpoint later. |
| D16 | Drift = standardised mean shift + out-of-range share; no Evidently | Two statistics answer the question; avoids a heavy dependency. |
| D17 | Optional Gemini explainer, off by default | Core platform fully local; LLM only rephrases stored facts and cannot act. |
