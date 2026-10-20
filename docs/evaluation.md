# Evaluation

All numbers below are produced by code in this repository and can be regenerated. Nothing is hand-entered.

## Model (NASA C-MAPSS FD001)

**Official test set** — prediction at the last observed cycle of each of 100 test engines vs `RUL_FD001` (raw truth):

| Model | RMSE | MAE | Bias (+ = late) | PHM08 score |
|---|---|---|---|---|
| LightGBM (selected) | 15.74 | 11.51 | +0.28 | 432 |
| Ridge baseline | 21.47 | 17.04 | +2.29 | 1,084 |
| Mean baseline | 43.01 | 35.90 | +11.08 | 32,901 |

Against truth capped at 125 (the training target): RMSE 14.55, MAE 10.44.

**Hold-out run-to-failure engines** (20 engines, all 4,104 cycles, capped truth): RMSE 14.70, MAE 10.06; when
true RUL ≤ 50: RMSE 8.23, MAE 5.91 (1,020 rows).

**Interval coverage** (nominal 90 %): test 0.89 (capped truth) / 0.82 (raw truth — engines with true RUL > 125 sit above
the capped target); hold-out 0.899 overall and 0.964 for RUL ≤ 50. Mean test interval width 43.5 cycles.

Context: published FD001 results for tree ensembles and deep sequence models typically report RMSE ≈ 12–18; this
model is in that band. No claim of state-of-the-art is made.

## TrustTwin gate sanity check
On clean hold-out data sampled every 7 cycles (585 assessments) the gate returned 525 VALID and 60 DEGRADED; every
DEGRADED came from the "history < 20 cycles" check (expected for new engines). No false OOD or spike flags.
Injected faults are covered by tests (missing sensors, NaN, non-numeric, 1e9, Kelvin-scaled temperatures, 40σ spikes,
stale timestamps, < 5 cycles of history).

## Planner
* 25 randomly generated instances × 2 solvers: zero hard-constraint violations by the independent verifier; CP-SAT
  objective ≤ greedy objective on every instance.
* Seeded demo backlog (9 work orders, 6 technicians, 7 parts): CP-SAT OPTIMAL, objective 1278 vs greedy 1292;
  the T50-probe work order is correctly delayed to its part arrival and reported late.

## Digital twin (simulated)
*Results from a simulated scenario, not demonstrated real-world fleet improvements.*
Default parameters, seed 2026: 10 aircraft × 2 engines, 120 days, 2 crews, 4 spare modules + 3 every 14 days (30 %
chance of a 10-day slip), 2 % daily sensor-dropout chance per engine, 5 % crew absence, 1-day review delay, replacement
trigger at interval lower bound ≤ 25 cycles, hold at ≤ 6.

| Metric | Reactive | Predictive |
|---|---|---|
| Unscheduled failures | 20 | 0 |
| Availability | 92.0 % | 92.2 % |
| Aircraft down-days | 96 | 94 |
| Planned replacements | 0 | 28 |
| Verification inspections (degraded inputs) | 0 | 36 |
| Job-days waiting for parts | 0 | 157 |
| Remaining life removed early (cycles) | 0 | 1,403 |

Across seeds 1 and 7 the pattern holds (failures ~19 → 0; availability within ±2.3 points, sometimes lower).
Interpretation: in this model predictive planning converts unscheduled failures into planned work but costs spares and
crew time; it is not a free availability gain. The simulator's failure cost is downtime only; it does not model
safety consequences, secondary damage or mission impact.

## Test coverage

`pytest` (65 tests) + Vitest (8 tests). Mandatory scenarios:

| # | Scenario | Test |
|---|---|---|
| 1 | NASA parsing | `ml/tests/test_ml.py::test_dataset_parsing` |
| 2 | Trains on actual data | `test_model_trains_on_real_data` |
| 3 | Saved model loads + infers | `test_saved_model_loads_and_infers` |
| 4 | Metrics from real predictions | `test_reported_test_metrics_match_real_predictions` |
| 5 | Engine-group leakage | `test_no_engine_leakage_between_splits`, `test_features_are_causal` |
| 6 | Missing sensor detected | `backend/tests/test_trust_planner_sim.py::test_missing_sensor_detected` |
| 7 | Stale data detected | `test_stale_data_detected` |
| 8 | Invalid input never trusted | `test_invalid_input_never_trusted` (4 cases), `test_unit_mismatch_flagged` |
| 9 | Part unavailability changes schedule | `test_part_unavailability_changes_plan`, `test_api.py::test_trusttwin_scenario_end_to_end`, `test_inventory_change_influences_planning` |
| 10 | Technician shortage | `test_technician_shortage_affects_schedule` |
| 11 | Mandatory constraints | `test_optimiser_enforces_hard_constraints` (25 random instances), `test_empty_queue_and_precedence`, `test_verifier_catches_violations` |
| 12 | Approval recorded | `test_api.py::test_operator_approval_recorded` |
| 13 | Unauthorised role cannot approve | `test_unauthorised_roles_cannot_approve` (technician, analyst) |
| 14 | Repeatable simulation | `test_simulation_repeatable_with_seed`, `test_scenario_reproducible` |
| 15 | Identical conditions | `test_policies_share_identical_conditions` |
| 16 | Persistence across restart | `test_data_persists_across_restart` (+ PostgreSQL run in docs/deployment.md) |
| 17 | Frontend API errors | `frontend/src/api.test.tsx` |
| 18 | No secrets in bundle | `npm --prefix frontend run check:secrets` (verified to catch a planted secret) |

Also covered: ingestion samples (accept/duplicate/conflict/reject counts, unit conversion, idempotent re-import),
audit-chain tamper detection, admin-only settings, CSV exports, Alembic migration vs models, login rate limiting.
