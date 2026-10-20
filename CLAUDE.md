# CLAUDE.md — AeroPulse AI

Advisory predictive-maintenance & fleet-availability platform for SIH26249 (MoD, India).
Requirements: [MASTER_PROMPT.md](MASTER_PROMPT.md) (authoritative, never shorten).
Context: [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) · Status: [PROGRESS.md](PROGRESS.md) · Decisions: [DECISIONS.md](DECISIONS.md)

## Session-start recovery checklist
1. `git remote -v` → must be `sahilkarande0918-cmd/AeroPulse-AI`, branch `main`.
2. Read CLAUDE.md, MASTER_PROMPT.md, PROJECT_CONTEXT.md, PROGRESS.md, DECISIONS.md.
3. `git status`, `git log -10 --oneline`, `git show --stat HEAD`.
4. Verify against code: `ml/artifacts/` exists? `pytest` passes? `npm run build` passes?
5. Continue from PROGRESS.md "Next steps". Update PROGRESS.md before ending.

## Stack
- `ml/` — Python 3.11, pandas, LightGBM, split-conformal intervals, SHAP (training). `python -m ml.train`
- `backend/` — FastAPI + SQLAlchemy 2 + Alembic + OR-Tools CP-SAT. Run: `.venv/Scripts/python -m uvicorn app.main:app --app-dir backend`
- Database: **Neon PostgreSQL** (hosted, `DATABASE_URL` in `.env`, sslmode=require) · local PostgreSQL via Docker for offline/on-prem · SQLite only for quick dev/tests. **No Supabase, ever.**
- `frontend/` — React + TS + Vite + Tailwind v4 + TanStack Query + Recharts + lucide-react.
- Docker Compose: postgres + backend + frontend (nginx).

## Rules
- **Ponytail (full) is mandatory**: reuse > stdlib > installed deps > minimal code. No speculative abstractions. Never skip required features, validation or security.
- Never fabricate metrics, predictions or charts. Every number is computed or labelled "synthetic/demo".
- Advisory only: never imply airworthiness/flight clearance. Prediction, recommendation, approval are separate entities.
- Fictional aircraft IDs only. C-MAPSS = simulated commercial turbofan data, not military.
- Git: use the configured identity as-is. **No AI co-author/attribution lines in commits. Never add AI bots as collaborators.** No force-push. Never commit secrets, `.env`, raw data, venvs.
- Run tests before claiming done: `.venv/Scripts/python -m pytest` (root) and `cd frontend && npm test && npm run build`.
