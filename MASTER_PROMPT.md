# MASTER BUILD PROMPT — AEROPULSE AI
## Smart India Hackathon 2026 | SIH26249
## AI-Powered Predictive Maintenance & Fleet Availability

> Authoritative requirements document. Saved verbatim from the project owner's original prompt (sections 1–25). Do not shorten or overwrite.

You are my principal software architect, senior full-stack engineer, ML engineer, AI safety engineer, DevOps engineer, and product design lead.

Your task is to independently design, implement, train, test, document, and prepare a working full-stack web application called:

**AeroPulse AI**

Tagline: "Predict Early. Maintain Smarter. Fly Ready."

This is a serious Smart India Hackathon project that may eventually be evaluated for real-world adoption by the Ministry of Defence, India.

Therefore, build a functional, technically defensible, extensible, pilot-oriented system, NOT a superficial hackathon UI.

You have permission to write code, install required open-source dependencies, download legally accessible public datasets, execute training scripts, create development databases, test, debug, and improve the application.

Do not stop after presenting a development plan. START IMPLEMENTING.

==================================================
1. OFFICIAL PROBLEM STATEMENT
==================================================

Problem ID: SIH26249

Title:
Air Power - Predictive Maintenance & Fleet Availability

Organisation:
Ministry of Defence (MoD), India

Department:
Defence Services Staff College

Category: SOFTWARE

Theme: Transportation & Logistics

Official description:

"Low aircraft availability due to fragmented and largely reactive maintenance practices across the air fleet. Maintenance data from aircraft health-monitoring systems, technical records, spares and maintenance agencies is not adequately integrated, resulting in delayed fault prediction, avoidable aircraft downtime and sub-optimal utilisation of critical assets."

Technology opportunity:
AI/ML-based predictive maintenance, IoT/aircraft health monitoring, digital twins and an integrated maintenance analytics platform.

Our software must address the COMPLETE problem, not just predict engine failures.

The final product should demonstrate:

1. Integration of fragmented maintenance information.
2. Machine-learning-based equipment degradation prediction.
3. Explainable aircraft component health assessments.
4. Maintenance planning and resource optimisation.
5. Spare-parts and technician availability integration.
6. Fleet health and maintenance readiness visibility.
7. Scenario-based evaluation of maintenance decisions.
8. Human-in-the-loop approval and accountability.
9. A credible pathway toward secure real-world deployment.

Our initial version uses publicly available simulated aircraft-engine data and explicitly labelled synthetic maintenance records.

Never claim that this prototype has been validated on military aircraft.

==================================================
2. TARGET GITHUB REPOSITORY — MANDATORY
==================================================

Work exclusively in:

https://github.com/sahilkarande0918-cmd/AeroPulse-AI.git

Repository name: AeroPulse-AI
Default branch: main

Clone the existing repository if necessary:

git clone https://github.com/sahilkarande0918-cmd/AeroPulse-AI.git

If already inside this repository, use the current working directory.

Verify git remote, branch, status and existing files before proceeding.

Do not create an unrelated project or publish to another repository.

The repository was initially empty.

IMPORTANT GITHUB CONTRIBUTOR REQUIREMENT:

- NEVER add Claude, Anthropic, Claude Code, any AI bot, or any automated assistant as a repository collaborator or contributor.
- NEVER add "Co-Authored-By: Claude" or AI attribution footers to commit messages.
- NEVER add AI assistant accounts to GitHub permissions.
- Do not modify or spoof the configured Git author identity.
- If the user's legitimate Git identity is already configured, use it normally for authorised commits.
- If no legitimate Git author identity is configured, leave changes uncommitted and explain the blocker.
- Do not force-push, rewrite history, or change repository visibility.
- Push completed code to the existing repository only when Git authentication and permission are available.
- Do not modify GitHub Actions or repository permissions to grant AI tools access.
- Respect third-party licences and maintain a THIRD_PARTY_NOTICES.md when incorporating third-party code.

The project remains under the ownership of the existing GitHub repository owner.

==================================================
3. COMPULSORY SKILLS AND REPOSITORY USAGE
==================================================

Before implementing, inspect the available Claude Code skills, plugins and project instructions.

A. PONYTAIL — COMPULSORY

Repository:
https://github.com/DietrichGebert/ponytail

This MUST be used throughout development.

If already installed, activate its appropriate full engineering mode.

Otherwise, use the officially documented Claude Code plugin installation process:

/plugin marketplace add DietrichGebert/ponytail
/plugin install ponytail@ponytail

These are Claude Code slash commands, not shell commands. If the current execution environment cannot install plugins programmatically, inspect the official Ponytail skill instructions and apply them directly for the session. Report whether the plugin itself is active.

Ponytail must guide implementation by encouraging:
- Minimal necessary complexity.
- Reusing established libraries.
- Avoiding duplicate code.
- Proper error handling and tests.
- Security-conscious engineering.
- Readable and maintainable code.
- Reviewing risky changes.
- Identifying technical debt.

Do NOT interpret minimal coding as permission to skip required features.

When available, use Ponytail review/audit commands after implementation.

B. FRONTEND DESIGN SKILL

Use the appropriate installed frontend-design skill.

Reference:
https://github.com/anthropics/claude-code/blob/main/plugins/frontend-design/skills/frontend-design/SKILL.md

Design a distinctive but restrained aviation maintenance operations interface.

C. OTHER SKILLS

Check the available skills for:
- Python engineering.
- Machine learning.
- Data science.
- React/TypeScript.
- UI/UX design.
- API architecture.
- Database development.
- Security review.
- Testing and debugging.
- Documentation.
- Deployment.

Use relevant available skills. Do not install arbitrary packages or untrusted skill repositories just for appearance.

D. USEFUL VERIFIED OPEN-SOURCE PROJECTS

Study and reuse appropriate libraries and documented examples:

Google OR-Tools:
https://github.com/google/or-tools

Official maintenance scheduling example:
https://github.com/google/or-tools/blob/stable/examples/python/jobshop_with_maintenance_sat.py

SHAP:
https://github.com/shap/shap

Evidently:
https://github.com/evidentlyai/evidently

Do not blindly copy complete unrelated repositories.

Prefer supported packages and official documentation. Verify licences, compatibility and necessity.

Do not use MiniMind for predicting numerical aircraft-engine degradation. It is a generative language-model project and is not appropriate for the core RUL regression task.

==================================================
4. CORE PRODUCT VISION
==================================================

AeroPulse AI is a unified, explainable aircraft maintenance decision-support platform.

The platform connects:

AIRCRAFT HEALTH DATA
        |
TECHNICAL MAINTENANCE RECORDS
        |
SPARE-PART INVENTORY
        |
MAINTENANCE PERSONNEL/CAPACITY
        |
        v
DATA VALIDATION AND INTEGRATION
        |
        v
ML HEALTH PREDICTION ENGINE
        |
        v
AEROPULSE TRUSTTWIN
        |
        v
CONSTRAINED MAINTENANCE PLANNING
        |
        v
HUMAN REVIEW AND APPROVAL
        |
        v
FLEET HEALTH, READINESS AND AUDIT DASHBOARD

Build this as a single cohesive product.

Use the terms "maintenance readiness" and "fleet availability" carefully. Do not suggest operational dispatch clearance, airworthiness certification, or permission for flight.

The software generates advisory maintenance intelligence only.

==================================================
5. FLAGSHIP DIFFERENTIATOR — AEROPULSE TRUSTTWIN
==================================================

THIS IS OUR MOST IMPORTANT DIFFERENTIATING FEATURE.

Name:
AeroPulse TrustTwin

Concept:
A confidence-aware, data-quality-aware maintenance decision twin capable of comparing actions under uncertainty and degraded information conditions.

Traditional predictive maintenance systems often show failure probability or RUL.

Our differentiator must answer:

"Can we trust this prediction, and what is the safest feasible maintenance response given the available resources?"

Build an operationally meaningful implementation with the following connected capabilities.

A. SENSOR RELIABILITY CHECKING

Detect:
- Missing sensor fields.
- Invalid numerical values.
- Unusually large sensor deviations.
- Stale timestamps.
- Insufficient history.
- Features outside expected training distributions.
- Schema or units mismatches.

Generate a structured data-quality assessment.

Never quietly convert unreliable sensor data into high-confidence predictions.

Show why data quality is degraded.

B. UNCERTAINTY-AWARE ML

Produce:
- A predicted RUL value in operating cycles.
- A calibrated uncertainty interval where technically feasible.
- Model version and dataset provenance.
- Important sensor feature contributions.
- Prediction reliability or quality state.

Prefer an interpretable uncertainty approach such as conformal calibration on a held-out calibration set, with measured coverage.

Do not invent statistical confidence values.

If calibration cannot be validated, show that limitation honestly.

C. CONFIDENCE-BASED ABSTENTION

Implement a prediction-gating policy.

Possible states:

VALID
Prediction accepted for advisory evaluation.

DEGRADED
Input data or model conditions are questionable. Manual verification recommended.

UNAVAILABLE
Prediction cannot responsibly be generated.

For invalid or severely out-of-distribution inputs, refuse to manufacture an RUL estimate.

Show the reason in the UI.

Thresholds must be configurable and clearly marked as prototype settings, not actual certified aircraft maintenance standards.

D. WHAT-IF MAINTENANCE SIMULATION

Create interactive scenarios such as:

Scenario 1:
A developing engine fault appears.

Scenario 2:
Required spare part is unavailable.

Scenario 3:
A maintenance technician becomes unavailable.

Scenario 4:
Important sensor readings disappear.

Scenario 5:
Multiple aircraft require inspections simultaneously.

When users change a scenario, recalculate the feasible maintenance plan and expected outcomes.

All simulations must be deterministic/reproducible when given the same seed, starting state and policy.

E. HUMAN-IN-THE-LOOP DECISIONS

Maintenance officers can:

- Review a prediction and evidence.
- Request inspection or further data.
- Approve or reject a proposed schedule.
- Enter a reason for an override.
- See who made the decision.
- Review the resulting maintenance audit log.

Prediction, recommendation and approval must be separate entities.

A model must NEVER independently authorise aircraft operation or final airworthiness decisions.

F. UNIQUE COMBINED DEMO

The strongest demo should be:

1. An aircraft engine exhibits developing degradation.
2. The trained ML model generates a prediction.
3. TrustTwin shows the supporting evidence and uncertainty.
4. A maintenance recommendation appears.
5. A spare part becomes unavailable.
6. The maintenance optimiser generates a new feasible plan.
7. A sensor dropout occurs.
8. TrustTwin flags the degraded prediction and requests verification.
9. A human officer reviews the new plan.
10. The platform records the decision and its consequences in the simulator.

Build this workflow end-to-end.

This is more important than a decorative 3D aircraft model.

==================================================
6. REAL ML MODEL TRAINING — MANDATORY
==================================================

You must PERSONALLY EXECUTE the ML development workflow using the available terminal, tools, Python environment and public data.

Do not just write scripts and claim the model has been trained.

Do not simulate an ML prediction with random numbers.

DATASET:

NASA C-MAPSS Turbofan Engine Degradation Simulation Dataset.

Official NASA repository:
https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/

Use the NASA "Turbofan Engine Degradation Simulation" dataset.

Official NASA download:
https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip

Official metadata:
https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data

First verify the dataset download and archive contents.

Start with FD001.

FD001:
- 100 training engine trajectories.
- 100 test engine trajectories.
- One operating condition.
- One simulated fault mode.

Explore other subsets only after FD001 works reliably.

IMPORTANT:
The underlying data represents simulated commercial turbofan engine degradation. It is NOT defence-specific or evidence of military equipment suitability.

DATA HANDLING:

Create a reproducible dataset pipeline.

Parse the actual files:
train_FD001.txt
test_FD001.txt
RUL_FD001.txt

Use correct column definitions:
- Unit ID.
- Operating cycle.
- Three operational settings.
- Twenty-one sensor measurements.

Verify the dataset schema before coding transformations.

Build preprocessing for:
- Missing or malformed values.
- Constant/low-information sensors.
- Causal rolling statistics.
- Sensor trends.
- Time-aware feature engineering.
- Engine-level grouping.
- Feature scaling where appropriate.

CRITICAL ANTI-LEAKAGE REQUIREMENTS:

- Never split random rows from the same engine into both training and validation.
- Keep engine trajectories grouped when evaluating generalisation.
- Never include future readings in an inference feature window.
- Never use true test-set RUL values as inference features.
- Fit preprocessing using training data only.
- Keep validation/calibration data isolated appropriately.

MODEL DEVELOPMENT:

Train and compare at least:
1. A simple baseline.
2. A LightGBM or XGBoost regression model.

Choose the best validated model, not the most sophisticated one.

Optional later experiment:
A PyTorch sequence model, but only if it demonstrates a genuine benefit.

For the first version, prefer CPU-compatible LightGBM.

The user's computer can run local training. Configure CUDA only when an actually compatible training method justifies it.

TARGET:
Remaining Useful Life in engine operating cycles.

Train, evaluate and save the model.

Report:
- Mean Absolute Error.
- Root Mean Squared Error.
- Prediction error distribution.
- Baseline comparison.
- Held-out evaluation protocol.
- Interval coverage if calibrated intervals exist.

Produce:
- model artifact.
- preprocessing artifact.
- feature schema.
- model version.
- training configuration.
- validation summary.
- reproducible training script.
- evaluation plots.
- machine-readable evaluation report.

Use SHAP where compatible to explain model behaviour.

Do not claim accuracy or gains without measured results.

If the NASA dataset download fails:
1. Retry the official source sensibly.
2. Check a legitimate accessible mirror with verified provenance and licensing.
3. Document what source was used.
4. Report any unresolved blocker accurately.

Synthetic demo records may support UI development but must never masquerade as a NASA-trained prediction.

Use real trained-model inference for the primary demonstration.

==================================================
7. TECHNICAL ARCHITECTURE
==================================================

Use the following preferred stack.

FRONTEND:
- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- shadcn/ui where appropriate.
- Lucide icons.
- React Router.
- TanStack Query.
- Recharts.
- Lightweight intentional animation where needed.

BACKEND:
- Python 3.11+.
- FastAPI.
- Pydantic.
- SQLAlchemy.
- Alembic.
- PostgreSQL.

ML:
- pandas.
- NumPy.
- scikit-learn.
- LightGBM/XGBoost.
- joblib.
- SHAP.
- Optional Evidently for drift detection.

OPTIMISATION:
- Google OR-Tools CP-SAT.

DATABASE:
Use PostgreSQL as the primary target.

Support local development through Docker Compose.

[Amended 2026-10-20, see section 26] Neon PostgreSQL is the primary hosted database for non-sensitive demonstrations, accessed only through standard PostgreSQL (SQLAlchemy + Alembic). The application must not depend on any provider-proprietary service.

The production architecture must support self-hosted PostgreSQL in a restricted or disconnected environment.

AI COPILOT:
An optional Gemini API integration for natural-language explanation of already computed, structured demo results.

The LLM must NEVER:
- Generate fake sensor readings.
- Replace the trained numerical prediction model.
- Invent maintenance procedures.
- Override maintenance rules.
- Make autonomous safety decisions.
- Receive classified or restricted data through a public API.

The core platform must run without an LLM API key.

DEPLOYMENT:
- Docker.
- Docker Compose.
- Linux-compatible services.
- Locally served frontend assets.
- Configurable environment variables.
- No compulsory external telemetry.
- No runtime dependency on cloud services for the core application.

Prefer a simple modular monolith over premature microservices.

Build a clean separation between:
- Data ingestion.
- Prediction and explanation.
- Trust assessment.
- Maintenance scheduling.
- Simulation.
- Persistence and audit.
- Web presentation.

==================================================
8. PRODUCT MODULES AND PAGES
==================================================

Build a coherent, responsive web application with the following modules.

PAGE 1 — COMMAND OVERVIEW

Show:
- Fleet inventory summary.
- Maintenance status distribution.
- Aircraft with active warnings.
- Outstanding inspections.
- Maintenance workload.
- Parts shortages.
- Latest prediction and data-quality status.
- Recent events.
- Simulated fleet availability trends.

Every metric must be computed from data or explicitly labelled as a demonstration example.

PAGE 2 — AIRCRAFT FLEET

Provide:
- Searchable/filterable fleet table.
- Fictional aircraft identifiers.
- Maintenance state.
- Last data update.
- Engine RUL estimate if available.
- TrustTwin validity state.
- Open maintenance tasks.
- Detailed aircraft view.

Use fictional identifiers only.

Never imply these are actual military aircraft.

PAGE 3 — AIRCRAFT HEALTH DETAIL

Show:
- Engine health history.
- Sensor time-series graphs.
- Degradation trends.
- RUL prediction.
- Calibrated uncertainty interval when available.
- Influential sensor readings.
- Data quality warnings.
- Model version and source.
- Relevant maintenance history.
- Ability to inspect prediction evidence.

Provide appropriate loading, unavailable, and error states.

PAGE 4 — PREDICTIVE INTELLIGENCE

Show:
- Actual model evaluation metrics.
- Baseline-versus-trained-model comparison.
- Error plots.
- Prediction distributions.
- Feature importance.
- Model provenance.
- Monitoring/drift summary if implemented.
- Explanation of how the model was trained and tested.

Never fabricate training charts.

PAGE 5 — MAINTENANCE PLANNER

Build a real working planning tool.

Include:
- Maintenance work orders.
- Expected task durations.
- Required technician skills.
- Technician availability.
- Spare-parts dependencies.
- Task precedence.
- Scheduling conflicts.
- Proposed inspection plans.
- Approval workflow.
- Schedule timeline or Gantt-style visualisation.

Use OR-Tools for genuine constrained planning.

A feasible solver result must reflect real input constraints.

If the constraints are infeasible, show why and provide actionable information.

PAGE 6 — SPARE PARTS

Include:
- Inventory list.
- Current stock.
- Reserved stock.
- Reorder thresholds.
- Expected replenishment date.
- Parts required by work orders.
- Shortage alerts.
- Links between spare shortages and affected maintenance tasks.

Changes to inventory must influence maintenance planning.

PAGE 7 — AEROPULSE TRUSTTWIN

Give this page special attention.

Include:
- Interactive simulated fleet.
- Selected aircraft and engine.
- Sensor reliability state.
- Prediction uncertainty.
- Adjustable scenario parameters.
- Spare-part disruption.
- Technician disruption.
- Sensor dropout.
- Baseline and revised plans.
- Explanation of recommended changes.
- Human-review state.
- Reproducible comparison outputs.

It must demonstrate real computation, not simply switch among predefined visual states.

PAGE 8 — REPORTS AND AUDIT

Show:
- Maintenance recommendations.
- Approval/rejection history.
- Operator comments.
- Model version used.
- Dataset/source reference.
- Timestamp of each action.
- Scenario comparisons.
- Exportable CSV and/or PDF reports.

Use append-only audit event behaviour at the application layer with appropriate access controls.

Do not claim the logs are cryptographically tamper-proof unless that property is actually implemented and validated.

PAGE 9 — SETTINGS / DATA CONNECTIONS

Include:
- Demo versus production-mode indications.
- Configured data sources.
- Sample CSV import.
- Validation status.
- Model information.
- Appropriate user-role settings.
- System health.
- Offline mode status.

Do not expose secrets.

==================================================
9. DATA INTEGRATION — ESSENTIAL
==================================================

The official problem emphasises fragmentation of maintenance data.

Therefore, a trained ML model plus dashboard is insufficient.

Implement adapters for at least:

A. Sensor time-series data.
B. Technical maintenance records.
C. Spare-part inventory.
D. Maintenance work orders.

Use CSV/JSON ingestion for the MVP.

Design typed interfaces for later integration with authorised operational systems.

Include:
- Schema validation.
- Units validation.
- Timestamp normalisation.
- Idempotent imports.
- Duplicate detection.
- Rejected-record reporting.
- Data provenance.
- Source identifiers.
- Ingestion logs.
- Versioned mapping configuration.

Never silently merge records with conflicting identities.

Use no real defence-system API or proprietary data without access and authorisation.

Create documented integration contracts that government engineers could adapt later.

==================================================
10. FLEET DIGITAL TWIN & POLICY COMPARISON
==================================================

Create an explicitly SIMULATED maintenance digital twin.

Model synthetic fleet entities:
- Aircraft.
- Engines.
- Health observations.
- Components.
- Maintenance jobs.
- Technicians.
- Spare parts.
- Work orders.
- Maintenance outcomes.

Build a deterministic scenario simulator with a configurable random seed.

Support at least two maintenance policies:

POLICY A:
Reactive maintenance.

POLICY B:
Predictive, human-reviewed maintenance planning.

Evaluate both policies under the same synthetic starting conditions and random events.

Report metrics such as:
- Maintenance downtime.
- Simulated fleet availability.
- Inspection workload.
- Unresolved maintenance events.
- Delayed tasks.
- Parts shortages.
- Uncertainty or rejected predictions.

All gains must be COMPUTED from the simulation.

Clearly label them:
"Results from a simulated scenario, not demonstrated real-world fleet improvements."

Avoid implying that a digital replica of a military aircraft has been validated.

==================================================
11. MAINTENANCE OPTIMISATION ENGINE
==================================================

Use Google OR-Tools.

Build a meaningful scheduling problem involving:
- Technician availability.
- Technician qualifications.
- Time-slot conflicts.
- Maintenance task dependencies.
- Spare-parts stock.
- Task duration.
- Priority categories.
- Maintenance windows.
- Human approval state.

Optimise a documented objective such as weighted maintenance lateness and resource utilisation, subject to hard constraints.

Keep objective weights and assumptions configurable.

Never violate hard constraints merely to display an attractive result.

Provide a transparent explanation of each suggested maintenance schedule.

For comparison, include a simple rule-based baseline scheduler.

Validate the optimiser by testing:
- Infeasible assignments.
- Missing technicians.
- Insufficient spare parts.
- Conflicting appointments.
- Task precedence.
- Empty work queues.
- Replanning after disruptions.

==================================================
12. VISUAL DESIGN — MINIMAL, PREMIUM, PROFESSIONAL
==================================================

This is an aircraft maintenance intelligence product.

The UI must look like a modern aviation engineering and operations console, not a gaming interface, hacker terminal, cryptocurrency dashboard or generic AI chatbot.

DESIGN DIRECTION:
"Precision aviation operations."

Primary theme: Dark, professional, calm, information-dense but readable.

Suggested palette:

Background navy: #0E1826
Surface slate: #172536
Elevated surface: #223449
Text white: #E8EFF5
Secondary text: #9EADBC
Technical blue: #4AB5D1
Healthy teal: #6ABFA3
Warning amber: #E7AF58
Critical red: #D97777

Use colours purposefully for operational status and data hierarchy.

TYPOGRAPHY:
- IBM Plex Sans or equivalent professional sans-serif.
- IBM Plex Mono for sensor values and numerical readouts.
- Clear number alignment.
- Restrained typography hierarchy.

LAYOUT:
- Collapsible left navigation.
- Slim top navigation/header.
- Clear page titles.
- Spacious but compact data panels.
- High-quality tables.
- Readable line charts.
- Clear status badges.
- Charts with labelled axes and units.
- Responsive layout.
- Accessible contrast and keyboard navigation.

DESIGN QUALITY:
- No excessive gradients.
- No neon-glow effects.
- No unnecessary glassmorphism.
- No huge decorative illustrations.
- No generic identical-card layouts everywhere.
- No cluttered dashboards.
- No random animated charts.
- No fake streaming data.
- No horizontal overflow.
- No overlapping cards, labels, charts, or controls.

Prefer actual maintenance information and charts over decoration.

Make the most distinctive screen the AeroPulse TrustTwin scenario workspace.

It should visually communicate:

Current health -> Prediction evidence -> Recommended action -> Resource constraints -> Revised plan -> Human approval.

Animations may be used to clarify changes, not as decoration.

Do not spend time building a 3D aircraft if the core functions are incomplete.

If feasible after core completion, build a modest interactive engine-health schematic using SVG.

Ensure consistent visual polish across all pages.

==================================================
13. ACCESS CONTROL, SECURITY AND DEPLOYMENT
==================================================

Design for a potential defence-sector pilot.

This does NOT mean claiming the project is certified, accredited or approved for classified use.

Implement sensible development-stage security.

Suggested user roles:
- Administrator.
- Maintenance Officer.
- Technician.
- Read-only Analyst.

Permissions must be enforced by the backend, not only hidden in the UI.

Protect:
- Data ingestion.
- Inventory modifications.
- Maintenance approvals.
- Administrative settings.
- Audit visibility.

Use secure password handling or an established authentication solution for local demonstration, with a clearly documented path to organisation-managed OIDC/SSO.

Use:
- Environment variables for secrets.
- Input validation.
- Restrictive CORS.
- Safe file uploads.
- Parameterised database access.
- Appropriate authentication checks.
- Basic rate limiting where justified.
- Dependency version management.
- Meaningful application logs.

No hardcoded real credentials.

No actual restricted defence information.

No default cloud uploads of operational data.

Ensure offline/on-premise functionality.

Document:
- Network dependencies.
- External API calls.
- Storage locations.
- Backup and recovery strategy.
- Database migrations.
- Installation requirements.
- Access control assumptions.

Make it easy for an authorised organisation to replace synthetic data sources with approved integrations.

==================================================
14. OPTIONAL AI MAINTENANCE COPILOT
==================================================

Only after the core trained model and optimiser work, consider a Gemini-powered assistant.

Purpose:
Explain structured predictions and maintenance recommendations in readable language.

Examples:
- Why has engine AP-004 received a maintenance warning?
- Which sensor trends most influenced this prediction?
- Why did the optimiser delay a maintenance task?
- Which spare shortage caused the schedule conflict?

The assistant must retrieve already verified structured system data.

Never let the LLM invent numerical results.

Never let it execute maintenance approvals or alter schedules without explicit authenticated user action.

Use a provider abstraction so the application can function without external generative AI services.

For development:
Gemini API may be optional.

For restricted production environments:
The default behaviour must remain fully local.

If no LLM credentials exist, gracefully hide or disable the optional assistant.

==================================================
15. CREDENTIALS AND ENVIRONMENT SETUP
==================================================

Create:
.env.example

Document all variables.

Potential variables include:

DATABASE_URL
JWT_SECRET_KEY
AUTH_MODE
GEMINI_API_KEY
LLM_ENABLED
CORS_ORIGINS
MODEL_PATH
DATA_DIRECTORY
APP_ENV
LOG_LEVEL

Use only variables actually required by the implementation.

Do not ask me for credentials at the beginning if you can complete meaningful work without them.

You do not need any external API key to train the NASA model.

Use local PostgreSQL through Docker Compose.

[Amended 2026-10-20, see section 26] For hosted Neon PostgreSQL, ask for:
- The Neon DATABASE_URL (connection string with sslmode=require), supplied via environment variable only.

Never commit credentials or service-role secrets.

If deployment requires:
- Vercel access.
- Railway/Render access.
- Neon DATABASE_URL.
- Gemini credentials.

Ask when that particular integration becomes necessary.

The application should run in local development without these external accounts.

==================================================
16. REQUIRED PROJECT STRUCTURE
==================================================

Use a practical monorepo, approximately:

AeroPulse-AI/
|
|-- frontend/
|   |-- src/
|   |-- public/
|   |-- package.json
|
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- services/
|   |   |-- database/
|   |   |-- core/
|   |-- tests/
|   |-- alembic/
|   |-- requirements.txt or pyproject.toml
|
|-- ml/
|   |-- data/
|   |-- scripts/
|   |-- features/
|   |-- artifacts/
|   |-- evaluation/
|   |-- tests/
|
|-- docs/
|   |-- architecture.md
|   |-- model-training.md
|   |-- evaluation.md
|   |-- deployment.md
|   |-- integration-guide.md
|   |-- security.md
|   |-- limitations.md
|   |-- demo-guide.md
|
|-- scripts/
|-- docker-compose.yml
|-- .env.example
|-- .gitignore
|-- README.md
|-- THIRD_PARTY_NOTICES.md

Adapt this structure if a simpler implementation provides the same separation and functionality.

Avoid unnecessary architectural abstractions.

Do not commit large training datasets, temporary outputs, secrets, caches or virtual environments.

If model files are too large for standard Git:
- Document their source.
- Provide a reproducible generation script.
- Consider Git LFS only if appropriate and configured.

==================================================
17. BACKEND API REQUIREMENTS
==================================================

Create well-structured, documented endpoints for:

- Health/status.
- Authentication and current user.
- Aircraft list/detail.
- Sensor history.
- Dataset and record ingestion.
- Predictions.
- Prediction evidence/trust assessment.
- Maintenance work orders.
- Proposed schedules.
- Approval and rejection.
- Spare-parts inventory.
- TrustTwin scenario simulation.
- Reports.
- Audit events.
- Model information.

Use OpenAPI documentation generated by FastAPI.

Use pagination/filtering for collections.

Provide consistent error schemas.

Include request validation and automated API tests.

Avoid exposing administrative actions through unprotected endpoints.

Do not create dummy endpoints that always return the same hardcoded success response.

==================================================
18. TESTING AND QUALITY GATES
==================================================

You are responsible for actually running tests.

BACKEND:
Use pytest.

FRONTEND:
Use Vitest or the project's appropriate testing setup.

END-TO-END:
Use Playwright if available and justified.

MODEL:
Create reproducibility and leakage checks.

Mandatory scenarios:

1. NASA dataset parsing succeeds.
2. Model trains on actual dataset.
3. Saved model loads and performs inference.
4. Test metrics are computed from real predictions.
5. Engine-group leakage is prevented.
6. Missing sensor data is detected.
7. Stale sensor data is detected.
8. Invalid input cannot produce a falsely trusted prediction.
9. Spare-part unavailability changes feasible scheduling.
10. Technician shortage affects the schedule.
11. Optimiser enforces mandatory constraints.
12. Operator approval is recorded.
13. Unauthorised role cannot approve plans.
14. Simulation produces repeatable results with fixed seed.
15. Reactive versus predictive comparison uses identical conditions.
16. Relevant data persists across service restart.
17. Frontend properly handles API errors.
18. No application secrets are exposed in client bundles.

Validate API/UI integration with the actual backend.

Never mark incomplete tests as passed.

Run:
- Type checking.
- Linting.
- Unit tests.
- Integration tests.
- Frontend production build.
- Available security checks.
- A local end-to-end smoke test.

Fix failures rather than simply documenting them as passing.

==================================================
19. REAL-WORLD IMPLEMENTATION ROADMAP
==================================================

This product may eventually be assessed for organisational use.

Therefore, create a realistic adoption roadmap.

STAGE 1:
Public NASA dataset and synthetic integration prototype.

STAGE 2:
Pilot using specifically authorised, non-classified representative equipment data and approved interfaces.

STAGE 3:
Independent validation of data mappings, models, uncertainty, failure modes and operational workflows.

STAGE 4:
Security review, local deployment, access controls, reliability testing, backup and recovery.

STAGE 5:
Controlled, supervised pilot with approved maintainers and defined success criteria.

STAGE 6:
Only after organisational acceptance, pursue required assurance and broader integration.

Clearly identify that real-world aircraft maintenance procedures, thresholds and authority must come from approved domain experts and regulations.

No system-level readiness improvement can be claimed solely from C-MAPSS evaluation.

Document the major domain-transfer challenge from simulated commercial turbofan data to any eventual real fleet.

==================================================
20. DOCUMENTATION REQUIREMENTS
==================================================

Write a polished README.

Include:
- Project overview.
- Official SIH problem alignment.
- Architecture diagram using Mermaid.
- Why AeroPulse AI is different.
- Real feature list.
- Data provenance.
- Training instructions.
- Evaluation results.
- Local installation.
- Docker instructions.
- Environment variables.
- API documentation.
- UI screenshots if capture is available.
- Security assumptions.
- Known limitations.
- Pilot implementation roadmap.

Create simple technical diagrams describing:

1. Overall system architecture.
2. ML training/inference pipeline.
3. TrustTwin decision flow.
4. Maintenance optimisation workflow.
5. Data integration architecture.

Create a concise SIH demo guide.

The demo must explain:
Problem -> Data -> Prediction -> Confidence -> Maintenance action -> Resource disruption -> Revised plan -> Evaluation -> Human approval.

Clearly distinguish finished features from planned features.

==================================================
21. EXECUTION ORDER — DO NOT SKIP
==================================================

PHASE 0 — INSPECTION AND PLANNING

- Confirm repository.
- Inspect environment and available skills.
- Activate Ponytail.
- Review applicable frontend-design skill.
- Verify dataset source.
- Check installed Python/Node/Docker versions.
- Prepare a compact implementation plan.
- Begin coding immediately.

PHASE 1 — FOUNDATION

- Create repository structure.
- Build FastAPI service.
- Configure database and migrations.
- Build frontend shell.
- Define typed models and API contracts.
- Add local run instructions.

PHASE 2 — ML DEVELOPMENT

- Download real NASA data.
- Inspect and preprocess the data.
- Implement baseline and trained model.
- Execute model training.
- Evaluate on held-out engines.
- Save artifacts and evaluation results.
- Expose real inference through backend API.

PHASE 3 — CORE MAINTENANCE SYSTEM

- Implement aircraft and health records.
- Add maintenance history and imports.
- Implement spare-parts records.
- Implement technician constraints.
- Build OR-Tools scheduling.
- Connect predictions to advisory work orders.

PHASE 4 — AEROPULSE TRUSTTWIN

- Validate input reliability.
- Implement uncertainty and gating.
- Implement simulated disruptions.
- Compare maintenance responses.
- Add approval workflow.
- Store evidence and audit records.

PHASE 5 — PROFESSIONAL UI

- Implement all important pages.
- Connect live backend data.
- Use the frontend-design skill.
- Improve charts, loading states and accessibility.
- Test responsiveness and interaction.

PHASE 6 — VALIDATION AND POLISH

- Run all tests.
- Fix integration issues.
- Verify reproducibility.
- Run Ponytail review/audit.
- Remove unused dependencies and dead code.
- Write documentation.
- Prepare reproducible demo.
- Build production frontend.
- Verify Docker startup.

Maintain working software at the end of each phase.

If context or execution limits prevent completing everything in one session, prioritise the core working product and preserve an exact progress report so work can continue without guesswork.

==================================================
22. SUCCESS ACCEPTANCE CRITERIA
==================================================

AeroPulse AI is not considered complete unless:

[ ] A working web application can be launched locally.

[ ] The frontend connects to real backend endpoints.

[ ] An actual NASA C-MAPSS model has been trained and saved.

[ ] Predictions come from the trained model, not randomly generated values.

[ ] Actual evaluation metrics are visible.

[ ] Aircraft health readings are visualised.

[ ] Maintenance and inventory records are integrated.

[ ] The OR-Tools maintenance planner enforces real constraints.

[ ] The TrustTwin detects unreliable inputs.

[ ] TrustTwin performs actual what-if calculations.

[ ] An inventory disruption changes maintenance planning.

[ ] Human approval and audit events work.

[ ] Reactive and predictive policies can be compared fairly.

[ ] The application works without a Gemini API key.

[ ] The core application can run without cloud dependencies.

[ ] Local deployment is documented and tested.

[ ] Technical and security limitations are stated truthfully.

[ ] No Claude/AI bot is added as a GitHub contributor or collaborator.

[ ] All completed tests have actually passed.

[ ] The application can demonstrate a coherent maintenance workflow.

==================================================
23. IMPORTANT RESTRICTIONS
==================================================

- DO NOT deliver a static landing page instead of a working application.
- DO NOT build the entire product as a chatbot.
- DO NOT invent model accuracy.
- DO NOT hardcode fake positive results.
- DO NOT claim military data access.
- DO NOT claim aerospace safety certification.
- DO NOT promise real fleet improvement without validation.
- DO NOT make automatic aircraft flight/airworthiness decisions.
- DO NOT transmit restricted operational data to public AI services.
- DO NOT require hardware for the software MVP.
- DO NOT prioritise decorative features over working intelligence.
- DO NOT clone unrelated GitHub repositories unnecessarily.
- DO NOT publish or modify permissions on other repositories.
- DO NOT add Claude or an AI bot as a contributor.
- DO NOT wait for my credentials when offline development is possible.
- DO NOT end with just a theoretical architecture.

Build working software.

==================================================
24. FINAL EXPECTED OUTPUT
==================================================

When the implementation is complete, give me:

1. Project completion summary.
2. The local repository location.
3. Git status and actual commit/push outcome.
4. Exact commands to start the application.
5. Which skills were activated, including Ponytail.
6. Trained ML model details.
7. Dataset source and measured metrics.
8. Feature-by-feature implementation status.
9. Test commands and real results.
10. Required credentials, if any.
11. Any unresolved blockers or limitations.
12. Deployment instructions.
13. SIH demonstration walkthrough.
14. Suggested next improvements for a defence-organisation pilot.

Be transparent about what was genuinely implemented, validated and deployed.

Do not claim tasks were completed without verifying them.

==================================================
BEGIN NOW
==================================================

Start by verifying the AeroPulse-AI repository, checking and activating Ponytail, inspecting the development environment, and downloading the NASA C-MAPSS dataset.

Then implement the project phase by phase.

The priority is a dependable engineering product with a trained ML model, working maintenance optimiser, and fully functional AeroPulse TrustTwin.

The frontend must be elegant, minimal and professional, but it must remain secondary to actual engineering correctness.

Build AeroPulse AI now.

==================================================
25. MANDATORY CONTEXT PERSISTENCE & SESSION RECOVERY
==================================================

IMPORTANT: This is a large, multi-session project. You MUST maintain persistent project memory inside the existing AeroPulse-AI GitHub repository so development can continue seamlessly after context compaction, session restarts, or token limits.

Repository:
https://github.com/sahilkarande0918-cmd/AeroPulse-AI.git

### Create and maintain these files:

1. **MASTER_PROMPT.md**
   - Save this entire original master prompt, including this section.
   - Preserve all requirements, features, architecture, constraints, and instructions.
   - Treat it as the project's authoritative requirements document.

2. **CLAUDE.md**
   - Concise instructions that Claude Code automatically reads when starting in the repository.
   - Project purpose, tech stack, coding rules, mandatory Ponytail skill, GitHub restrictions, and links to the other context files.
   - Include a session-start recovery checklist.

3. **PROJECT_CONTEXT.md**
   - What AeroPulse AI is and which SIH problem it solves.
   - Architecture, core modules, dataset, ML model, unique TrustTwin feature, and design decisions.
   - Important decisions and reasons behind them.

4. **PROGRESS.md**
   - Completed tasks.
   - Currently active tasks.
   - Pending tasks.
   - Known bugs and blockers.
   - Last verified test results.
   - Exact next steps.
   - Update after every major development phase and before ending a session.

5. **DECISIONS.md**
   - Record major architectural and technical decisions.
   - Explain why specific technologies or approaches were chosen.

### MANDATORY SESSION RECOVERY PROTOCOL

Whenever a new Claude Code session starts or context gets compacted:

1. Verify the current AeroPulse-AI repository and branch.
2. Read CLAUDE.md and MASTER_PROMPT.md.
3. Read PROJECT_CONTEXT.md, PROGRESS.md, and DECISIONS.md.
4. Run `git status`, `git log -10 --oneline`, and inspect the latest relevant commit changes using `git show` or `git diff`.
5. Inspect the actual source code, model artifacts, tests, and repository structure to verify progress.
6. Cross-check documented progress against the latest commits and uncommitted changes.
7. Identify the last genuinely completed milestone and the next unfinished task.
8. Continue implementation from that point without unnecessarily restarting or duplicating completed work.

### CONTINUOUS UPDATE RULES

- Update PROGRESS.md whenever a substantial feature or phase is completed.
- Update PROJECT_CONTEXT.md when architecture or scope changes.
- Update DECISIONS.md when important technical decisions are made.
- Keep CLAUDE.md short and easy to scan.
- Never overwrite the original master prompt with a shortened summary.
- Before context compaction or session termination, save the current state and precise next steps.
- Commit these documentation updates alongside relevant code when authorised.
- Never add Claude/Anthropic/AI bot contributor attribution or modify the legitimate Git author identity.
- Never store passwords, API keys, tokens, or secrets in these files.
- If Git history conflicts with documentation, inspect the actual code and tests before deciding what is complete.

**CRITICAL: Treat repository files, actual code, latest commits, and test results as your persistent source of truth—not your temporary conversation memory.**

Your objective is to continue building AeroPulse AI until the agreed requirements are implemented and verified, regardless of how many Claude Code sessions are required.

==================================================
26. AMENDMENT (2026-10-20) — DATABASE BACKEND: NEON POSTGRESQL
==================================================

Issued by the project owner after section 25. Supersedes every earlier mention of Supabase.

- Do NOT use Supabase anywhere in this project (no dependencies, configuration or references).
- Use Neon PostgreSQL as the primary hosted database backend, with Python FastAPI handling APIs, ML inference, maintenance optimisation and business logic.
- Integrate Neon through SQLAlchemy and Alembic.
- Use Neon for aircraft records, predictions, maintenance schedules, inventory, users and audit logs.
- Keep the connection secure using environment variables (DATABASE_URL); never commit it.
- Ask the project owner for the Neon DATABASE_URL when required.
- Maintain a local PostgreSQL option through Docker for offline/on-premise defence deployment.
- Preserve all existing functionality, ML training, TrustTwin and UI requirements; do not restart completed work.
