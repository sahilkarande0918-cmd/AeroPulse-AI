# Third-party notices

AeroPulse AI uses the following third-party data and open-source components. No third-party source code is copied
into this repository; components are installed as dependencies. Licences as published by each project.

## Data
| Item | Source | Terms |
|---|---|---|
| NASA C-MAPSS Turbofan Engine Degradation Simulation Data Set (FD001) | NASA Prognostics Center of Excellence, https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/ | Public NASA data. Cite: A. Saxena, K. Goebel, D. Simon, N. Eklund, "Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation", Int. Conf. on Prognostics and Health Management, 2008. `ml/artifacts/holdout_trajectories.csv.gz` is a derived subset (20 training engines). |

## Python
| Package | Licence |
|---|---|
| FastAPI, Starlette | MIT / BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| Pydantic, pydantic-settings | MIT |
| SQLAlchemy, Alembic | MIT |
| psycopg 3 | LGPL-3.0 (used unmodified as a library) |
| PyJWT | MIT |
| bcrypt | Apache-2.0 |
| python-multipart | Apache-2.0 |
| httpx | BSD-3-Clause |
| tzdata | Apache-2.0 |
| pandas, NumPy, scikit-learn, joblib | BSD-3-Clause |
| LightGBM | MIT |
| Google OR-Tools | Apache-2.0 |
| SHAP (training only) | MIT |
| Matplotlib (training only) | Matplotlib License (PSF-based) |
| pytest, Ruff (development) | MIT |

## JavaScript / fonts
| Package | Licence |
|---|---|
| React, React DOM | MIT |
| React Router | MIT |
| TanStack Query | MIT |
| Recharts | MIT |
| lucide-react | ISC |
| Tailwind CSS, @tailwindcss/vite | MIT |
| Vite, Vitest, Testing Library, jsdom, TypeScript, ESLint | MIT / Apache-2.0 / BSD |
| IBM Plex Sans / Mono (via @fontsource, MIT packaging) | SIL Open Font License 1.1 |

## Runtime images
| Image | Licence |
|---|---|
| postgres:16-alpine | PostgreSQL License |
| nginx:1.27-alpine | BSD-2-Clause |
| python:3.11-slim, node:22-alpine | PSF / MIT (plus OS package licences) |

## Design and engineering guidance
Development followed the Ponytail engineering skill (DietrichGebert/ponytail) and the Hallmark design skill as
guidance only; no code or assets from them are included.
