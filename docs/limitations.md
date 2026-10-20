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
* The deployed model is FD001 only. FD002–FD004 are benchmarked (`python -m ml.benchmark`) with per-condition
  normalisation: LightGBM RMSE 26.4 / 17.1 / 27.0, better than Ridge but well short of published deep-learning results on
  the multi-condition subsets. Not used in the application.

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
* Single-process rate limiting. OIDC bearer-token mode is implemented and tested with generated keys, but has not been
  connected to a real identity provider; the browser login flow relies on an OIDC reverse proxy.
* **Render Free (public demo):** 0.1 CPU makes CPU-heavy actions noticeably slower than on a laptop (see
  docs/deployment.md for measured numbers); the service sleeps after 15 min without traffic unless the UptimeRobot
  monitor keeps it warm, and a cold start takes about a minute. For a lag-free in-person demo use local Docker mode.
* Audit chain is tamper-evident, not tamper-proof.
* PDF export is the browser's "Save as PDF" with a dedicated print stylesheet (light theme, no navigation); CSV is the
  structured export.
* The optional LLM explainer (backend + UI panel, hidden when disabled) is tested against a mocked Gemini endpoint but
  has not been exercised against a live Gemini key.
* The frontend JavaScript bundle is ~830 KB (Recharts); acceptable on a local network, not optimised for low bandwidth.

## Finished vs planned
| Finished and tested | Planned |
|---|---|
| FD001 model, conformal intervals, SHAP; FD001–FD004 benchmark | Multi-condition production model; sequence models only if they beat LightGBM under the same protocol |
| TrustTwin gate + scenarios + review | Multivariate OOD, sensor-specific reliability models |
| CP-SAT planner + verifier + baseline | Bays/tooling, multi-skill crews, rolling-horizon re-planning |
| Ingestion for 4 sources | Scheduled pulls from authorised systems, mapping UI |
| RBAC, JWT, audit chain, OIDC bearer mode | IdP integration in a real organisation, WORM audit anchoring, accredited review |
| Docker (local PostgreSQL / Neon), Render + Vercel free hosting, uptime monitor | Kubernetes / air-gapped install bundle, metrics stack |
