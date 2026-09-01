# TelemetryX

TelemetryX is a portfolio-quality predictive-maintenance system for Remaining Useful Life (RUL) analysis using NASA C-MAPSS aircraft-engine simulation data. Phase 1 provides only the local development foundation: FastAPI, PostgreSQL, Redis, Dramatiq, Next.js, migrations, logging, health checks, and smoke tests.

No C-MAPSS ingestion, ML/RUL model, dashboard features, or authentication are implemented in this phase.

## Prerequisites (Windows / PowerShell)

Install the following tools and confirm them from a new PowerShell window:

```powershell
uv --version
pnpm --version
docker --version
docker compose version
```

The project targets Python 3.12 (managed by `uv`) and Node.js 22 LTS. If `pnpm` is unavailable after installing Node.js, enable Corepack:

```powershell
corepack enable
corepack prepare pnpm@latest --activate
```

If the `pnpm` shim is unavailable because the Node installation is managed or locked down, replace `pnpm` in the frontend commands below with `corepack pnpm`.

## First-time setup

From the repository root:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose exec api uv run alembic upgrade head
```

Open:

- Frontend: http://localhost:3000
- API documentation: http://localhost:8000/docs
- API liveness: http://localhost:8000/api/v1/health/live
- API readiness: http://localhost:8000/api/v1/health/ready

View logs:

```powershell
docker compose logs -f api worker web
```

Stop the environment:

```powershell
docker compose down
```

To remove local containers **and the local database volume**:

```powershell
docker compose down --volumes
```

## Local verification commands

Backend, from `backend`:

```powershell
Set-Location backend
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy app
```

Frontend, from `frontend`:

```powershell
Set-Location frontend
pnpm install
pnpm test
pnpm typecheck
pnpm build
```

## Repository layout

```text
backend/      FastAPI, Dramatiq, Alembic migrations, backend tests
frontend/     Next.js + TypeScript shell and frontend smoke test
data/         Local raw/processed files plus versioned sample fixtures
models/       Local model artifacts (ignored except .gitkeep)
infra/docker/ Container definitions
docs/         Architecture, data dictionary, provenance, and ADRs
```

## Phase 1 services

- `db`: PostgreSQL 16 local metadata database.
- `redis`: Dramatiq message broker.
- `api`: FastAPI API with JSON logs and `X-Request-ID` correlation IDs.
- `worker`: Dramatiq worker with a foundation smoke task.
- `web`: Next.js/TypeScript shell.

The only database migration creates `system_metadata`, a foundation table proving the migration workflow. Domain tables begin in the FD001 ingestion phase.

