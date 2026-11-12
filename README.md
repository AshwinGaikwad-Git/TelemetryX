# TelemetryX

TelemetryX estimates turbofan-engine Remaining Useful Life (RUL) in operating cycles from C-MAPSS-shaped telemetry. It includes file validation and provenance, reproducible feature snapshots, group-held-out ML experiments, nominal prediction intervals, feature evidence, and a four-tab inspection dashboard.

**Data identity:** Quick Demo Setup uses locally generated synthetic fixtures, not the official NASA FD001 files. Official files can be imported separately. Synthetic-demo results are not official NASA benchmark results. Risk bands are illustrative; outputs are simulated research analysis, not aircraft maintenance or dispatch authorization.

## Stack and workflow

- Python 3.12, FastAPI, SQLAlchemy/Alembic, pandas, scikit-learn HistGradientBoosting, SHAP.
- Next.js 15, React 19, TypeScript, Tailwind and Recharts; server data currently uses the typed fetch client and React state.
- SQLite for explicit local development, PostgreSQL for Compose; local background executor or Dramatiq/Redis workers.

Import train/test/test-RUL files -> inspect validation -> prepare/seal a dataset -> split raw training engines -> fit preprocessing on the training partition -> train/evaluate -> score final test cycles -> inspect predictions and explanations.

Training supports `gradient_boosting` and a `naive` median-training-row-capped-RUL baseline. The target cap defaults to 125. The point estimator uses squared-error loss; separate 0.05/0.95 quantile estimators produce nominal 90% prediction intervals. Observed coverage and mean interval width are reported separately for held-out validation cycles and final test cycles. No calibration guarantee is implied.

## Local Windows setup

Run from the repository root, in separate terminals. Install Python 3.12/uv and Node.js/pnpm first.

Backend:
```powershell
Set-Location backend
uv sync --all-groups
$env:DATABASE_URL = "sqlite:///telemetryx_dev.db"
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:
```powershell
Set-Location frontend
corepack pnpm install
corepack pnpm dev
```

Open http://localhost:3000. API docs: http://localhost:8000/docs.

The local executor runs jobs outside request handlers in one background thread. Use only **one API process** in local mode. On API restart, queued jobs resume; interrupted running jobs become failed and can be retried. The dashboard reconnects to its most recent job after a page reload. A multi-step demo interrupted between jobs can be continued using the registry's prediction action.

Database selection is explicit. An unavailable PostgreSQL server does not silently switch to another database. Apply Alembic migrations before starting the API, including for SQLite.

## Upgrading an existing local database

An older build may have created SQLite tables without an Alembic revision. The migration helper verifies the known legacy columns, creates a SQLite backup in `data/backups`, applies the additive migration and verifies existing row counts:

```powershell
Set-Location backend
uv run python -m scripts.migrate_local
```

It refuses an unrecognized legacy schema instead of stamping it blindly. The database backup is ignored by Git; retain it locally for rollback.

For an already Alembic-managed database, run only `uv run alembic upgrade head`. Revision `20261113_0003` adds job input/result columns and preserves existing rows. Existing models remain historical; train a new experiment to obtain the corrected validation preprocessing and interval metrics.

## Docker Compose

```powershell
Copy-Item .env.example .env
# Start dependencies and migrate before starting the API/worker.
docker compose up -d db redis
docker compose run --rm api uv run alembic upgrade head
docker compose up --build -d
```

Compose selects `JOB_BACKEND=redis`. API and worker share raw/processed/model storage. The worker is configured with one process/thread for the MVP. PostgreSQL and Redis readiness checks gate startup.

## Custom imports and immutable versions

In Dataset Explorer, select **Create a new dataset version**, choose `train`, and upload its text file. Uncheck the new-version option to add `test`, then `test_rul` to that draft. RUL labels require test telemetry first and align to consecutive test unit IDs starting at 1. Inspect each file's validation report and checksum before selecting **Prepare, train and predict**.

A validated role cannot be replaced within a version. Identical content is reused without changing engine IDs. Preparing seals the version against further imports; changed files require a fresh version. Original bytes are stored under content hashes. Source and experiment feature CSV/JSON snapshots are stored under distinct feature-set IDs with checksums. An experiment's manifest records its exact train/validation engine split, scaler statistics, selected sensors, RUL cap and source checksum.

## API

All paths are under `/api/v1`. Long operations return **202** with a job ID, status, attempt count, error and result. Poll `/jobs/{id}` for completion. Validation failure is a failed job with `result.report.errors`, not successful ingestion.

| Method | Path | Behavior |
|---|---|---|
| GET | `/health/live`, `/health/ready` | Liveness and database connectivity |
| POST | `/datasets` | Create a fresh FD001 draft |
| GET | `/datasets`, `/datasets/{id}` | Dataset metadata and per-file reports/checksums |
| POST | `/datasets/imports` | Multipart upload (`file`, `dataset_id`, `file_role`) and import job |
| POST | `/datasets/sample` | Synthetic fixture import/preparation job |
| POST | `/datasets/{id}/prepare` | Seal source and persist a feature snapshot |
| GET | `/datasets/{id}/engines` | Optional `role`, `model_version_id` filters |
| GET | `/engines/{id}` | Inspection, optional `model_version_id` |
| GET | `/engines/{id}/cycles` | `start_cycle`, `end_cycle`, `offset`, `limit` (max 10000) |
| GET/POST | `/experiments` | List experiments / enqueue training |
| GET | `/experiments/{id}` | Split/config and registered model |
| GET | `/models`, `/models/{id}` | Registry and artifact manifest |
| POST | `/models/{id}/predictions` | Prediction job (`dataset_id`, `role=train/test`) |
| GET | `/predictions`, `/predictions/{id}` | Stored prediction evidence and recommendations |
| GET | `/evaluations` | Distinct validation/test reports, including interval coverage |
| GET | `/dashboard/summary` | One dataset/model scope (`dataset_id`, `model_version_id`); test engines only |
| GET | `/jobs/{id}` | Poll a job |
| POST | `/jobs/{id}/retry` | Replay a failed job |
| POST | `/jobs/{id}/cancel` | Cancel a queued job |

Sample/import/training requests accept `Idempotency-Key`. Reusing a key with different inputs is rejected. Transient storage/database failures retry with bounded backoff up to `JOB_MAX_ATTEMPTS`; validation errors do not automatically retry. Results and inputs persist in the database. Jobs are not distributed exactly-once transactions: a crash after a service commit can leave completed outputs without a recorded job result. Inspect outputs before manual replay.

After an abrupt Redis worker termination, stop all workers, run `uv run python -m app.workers.recover`, restart workers, and retry the interrupted job through the API. This recovery operation must not run while workers are executing. Queued Redis deliveries remain broker-managed.

## Configuration

Settings are read from environment variables or `backend/.env` relative to the backend working directory. Compose reads the root `.env`. `RAW_STORAGE_PATH`, `PROCESSED_STORAGE_PATH`, `MODEL_STORAGE_PATH`, `MAX_UPLOAD_SIZE_MB`, `JOB_BACKEND`, `JOB_MAX_ATTEMPTS`, `DATABASE_URL`, `REDIS_URL` and CORS origins are applied. Local storage defaults to repository data/model folders; Compose uses mounted `/data` and `/models` paths. Upload filenames are display metadata and never choose filesystem paths.

## Verification

```powershell
Set-Location backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

```powershell
Set-Location frontend
corepack pnpm test
corepack pnpm typecheck
corepack pnpm build
```

Backend tests use temporary databases/storage and never ingest into your development database or overwrite your model files. Regression coverage includes holdout-only preprocessing, immutable byte-preserving imports, artifact compatibility, jobs/retries, migration preservation, interval metrics and dataset/model scoping. Frontend tests cover jobs, multipart imports, demo orchestration and error presentation.

Authentication, multi-user access, sequence neural models, CI/Playwright automation and production deployment hardening remain outside this implementation. See [architecture](docs/architecture.md), [data dictionary](docs/data-dictionary.md) and [data provenance](docs/cmapss-provenance.md).
