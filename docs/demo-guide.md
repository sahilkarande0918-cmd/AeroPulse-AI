# SIH demo guide (8–10 minutes)

Story arc: **Problem → Data → Prediction → Confidence → Maintenance action → Resource disruption → Revised plan →
Evaluation → Human approval.** Sign in as `officer`. Keep one line ready: *"Advisory only — the model never authorises
an aircraft."*

| # | Show | Say |
|---|---|---|
| 1 | **Command overview** | SIH26249: availability suffers because maintenance data is fragmented and practice is reactive. This console fuses sensor streams, technical records, spares and work orders. Fleet is synthetic; engine data is real NASA C-MAPSS. |
| 2 | **Settings → Import** `sensor_readings.csv` | Fragmentation is a data problem first: schema + units checked, Kelvin converted, duplicate skipped, conflicting record *rejected not merged*, unknown asset refused. Re-upload → "already imported". |
| 3 | **Predictive intelligence** | Trained here on FD001, engine-grouped split. LightGBM RMSE 15.7 vs Ridge 21.5 on NASA's test set; 90 % intervals measured at 89 % coverage. Nothing on this page is typed in by hand. |
| 4 | **Fleet → AP-101** | Engine AP-ENG-01: RUL ≈ 13 cycles, interval [0, 26]. Every TrustTwin check passes; SHAP shows which sensor trends drive it. Recommendation: plan hot-section replacement. |
| 5 | **TrustTwin**, AP-101 · AP-ENG-01, no disruption → *Run* | Baseline: VALID prediction → replacement task placed by CP-SAT; risk margin shown. |
| 6 | Toggle **Spare part unavailable** → *Run* | Kit stock 0, resupply slips 10 days: the optimiser cannot place the replacement inside the horizon — it says exactly why, and the risk table turns red. No constraint is bent to make it look good. |
| 7 | Add **Sensor readings disappear** → *Run* | T50 and Ps30 vanish: TrustTwin downgrades to DEGRADED, carries values forward visibly, and recommends inspection/verification first — which *is* schedulable. With three sensors missing it refuses to produce an RUL at all. |
| 8 | Scroll: **Why the plan changed**, Gantt baseline ↔ revised, diff | Deterministic explanation from computed results (no LLM). Same seed + inputs → same result hash. |
| 9 | **Officer review** → reject revised plan with a reason, approve the recommendation | Prediction, recommendation and approval are separate records. Analysts can run scenarios but cannot approve (403 from the API, not just a hidden button). |
| 10 | **Reports & audit** → *Verify chain*, export CSV | Who decided what, when, why, with which model version and data source. Hash chain: tamper-evident. |
| 11 | **TrustTwin → policy comparison** | Same seed and events for both policies. Predictive removes the 20 unscheduled failures, but availability is flat (92.0 → 92.2 %) because early replacements consume spares. We report that honestly — it is a simulation, not a promised gain. |
| 12 | Close on **roadmap** (README) | Next: authorised non-classified data, independent validation, accredited security, supervised pilot. |

## Reset between rehearsals
Easiest (local Docker demo and the hosted demo): sign in as `admin` → Settings & data → **Reset demo data** (deletes all
records and re-seeds a fresh fleet with timestamps anchored to now; enabled by `DEMO_RESET_ENABLED=true`). Do this
before judging on a deployment that has been running for days, otherwise TrustTwin rightly flags the replayed data as
stale.

Local dev: delete `backend/aeropulse_dev.db`, then `python manage.py migrate && python manage.py seed`.
Docker (local database, recommended for live demos): `docker compose -f docker-compose.yml -f docker-compose.local.yml down -v` then `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d` (≈ 30 s, clean seeded fleet).
Neon (destructive — deletes all AeroPulse tables in that database): `cd backend && alembic downgrade base`, then
`python manage.py migrate && python manage.py seed`.

## Likely judge questions
* *Is this validated on IAF aircraft?* No. Public simulated commercial-engine data; domain transfer is the main open problem (docs/limitations.md).
* *Why not deep learning?* Under the same engine-grouped protocol LightGBM already sits in the published FD001 range, is CPU-only and exactly explainable. A sequence model is worth adding only if it beats it on that protocol.
* *What if sensors lie?* That is TrustTwin's job: plausibility, units, spikes, staleness, OOD — and abstention.
* *Can it run disconnected?* Yes: local PostgreSQL profile, self-hosted fonts, no runtime calls (LLM off by default).
