# Limitations (stated plainly)

## Data and model
* **Domain transfer is the central open problem.** C-MAPSS FD001 is *simulated commercial* turbofan data: one
  operating condition, one fault mode (HPC degradation), 21 idealised sensors, run-to-failure trajectories with a clean
  failure definition. Real military fleets have different engines, sensor suites, sampling, units, operating regimes,
  maintenance interventions, censored histories and multiple interacting failure modes. The trained model must not be
  applied to any real aircraft; a pilot requires retraining and independent validation on authorised data.
* The model uses `cycle` (engine age since the start of the record) as a feature; C-MAPSS engines start with unknown
  initial wear, but real engines with overhaul history would need a different age definition.
* Target capped at 125 cycles: predictions above ~125 mean "healthy, not yet identifiable", not an exact life.
* Conformal intervals assume exchangeability between calibration and future data. Rows within one engine are
  correlated, and degraded/out-of-distribution inputs void the guarantee — which is why TrustTwin labels such cases.
  Coverage is measured (0.89 test, 0.90 hold-out), not guaranteed.
* Only FD001 is used. FD002–FD004 (multiple conditions / fault modes) are not yet modelled.

## TrustTwin and recommendations
* Thresholds (staleness, spikes, OOD share, RUL bounds) and the action catalogue are **prototype settings**, not
  certified maintenance standards. Real limits must come from approved maintenance data and authorities.
* The OOD check is per-feature range-based, not a multivariate density model.
* Recommendations are rules on top of the prediction; they are advisory and require an officer's decision.

## Planning
* Hour-granularity, 14-day horizon, shifts in IST without overnight shifts, one task per aircraft at a time, no bay or
  tooling capacity, no task splitting across shifts, deterministic durations.
* Part stock is a single pool (no locations, no serial tracking, no cannibalisation).

## Simulator
* Deliberately simple daily model; failure cost = downtime only (no safety, secondary damage or mission impact); fixed
  utilisation; replacement engines replay hold-out trajectories from cycle 1. Results show *mechanisms*, not
  expected real-world gains, and are labelled as simulated everywhere.

## Platform
* Single-process rate limiting; local authentication only (OIDC path documented, not implemented).
* Audit chain is tamper-evident, not tamper-proof.
* PDF export uses the browser's print dialog; CSV is the structured export.
* The optional LLM explainer is implemented but has not been exercised against a live Gemini key in this repository.
* The frontend JavaScript bundle is ~830 KB (Recharts); acceptable on a local network, not optimised for low bandwidth.

## Finished vs planned
| Finished and tested | Planned |
|---|---|
| FD001 model, conformal intervals, SHAP | FD002–FD004, sequence models only if they beat LightGBM under the same protocol |
| TrustTwin gate + scenarios + review | Multivariate OOD, sensor-specific reliability models |
| CP-SAT planner + verifier + baseline | Bays/tooling, multi-skill crews, rolling-horizon re-planning |
| Ingestion for 4 sources | Scheduled pulls from authorised systems, mapping UI |
| RBAC, JWT, audit chain | OIDC/SSO, WORM audit anchoring, accredited review |
| Docker (local PostgreSQL / Neon) | Kubernetes / air-gapped install bundle, monitoring stack |
