# TelemetryX Technical Specification

**Status:** Core MVP implemented; see implementation notes below
**Version:** 0.3
**Scope:** Portfolio-quality ML system for aircraft-engine degradation analysis and Remaining Useful Life (RUL) prediction using NASA C-MAPSS

## Implementation notes (2026-11-13)

An industrial pilot now extends this research specification: company membership, machinery/sensor registration, timestamped telemetry, quality/freshness, rule-based alerts, work orders and audit history. Its implemented scope and remaining work are described in docs/industrial-pilot.md. Research models remain isolated at /demo.

The remaining sections preserve the approved product design. Current behavior and commands are in README.md and docs/architecture.md. Implemented: immutable FD001 imports, feature snapshots, preprocessing fitted after group splitting, naive/gradient boosting models, nominal intervals with measured coverage, labelled explanation fallback, background job polling/retry/cancel, custom uploads and scoped dashboards.

Deferred: TanStack Query integration, complete shadcn/form-library integration, authentication, GitHub Actions and Playwright. Local execution uses one API process and a background thread; Compose runs Dramatiq/Redis. Redis crash recovery is operator-assisted. Synthetic-demo results do not establish official benchmark performance. Intervals have no calibration guarantee.

## 1. Product definition and MVP scope

TelemetryX is an ML-driven predictive-maintenance system. Its initial implementation ingests NASA C-MAPSS turbofan-engine simulation data, prepares run-to-failure sequences, estimates each engine's remaining useful life (RUL), evaluates model quality, explains individual predictions, and presents maintenance risk in a dashboard.

The first asset is an **aircraft turbofan engine** represented by a unit identifier and ordered operating cycles. The core design remains extensible for future industrial telemetry sources, but pump-specific data models, rules, and dashboard terminology are not part of this MVP.

### In scope

- Ingestion of NASA C-MAPSS train, test, and test-RUL files.
- Dataset metadata, file provenance, validation, and repeatable preprocessing.
- Engine/run health and degradation feature analysis.
- RUL target construction for training data and labelled evaluation for test data.
- An explainable gradient-boosting RUL baseline, model registry, and reproducible evaluation.
- Prediction explanations and uncertainty/risk bands.
- Fleet, engine, model-evaluation, and prediction-detail dashboard views.
- Versioned synthetic C-MAPSS-shaped fixtures for tests and demonstrations.
- Local Docker development, automated tests, and CI.

### Explicitly out of scope for the initial MVP

- Direct aircraft, SCADA, IoT, MQTT, OPC-UA, or streaming integrations.
- Real-time safety-critical maintenance decisions or automated work-order creation.
- A claim that the model is approved for aircraft operations; C-MAPSS is simulated benchmark data.
- User login, multi-tenancy, SSO, billing, and production notification integrations.
- A generic industrial-pump anomaly dashboard. Future telemetry adapters may add these domains without changing the C-MAPSS MVP.

## 2. Technology choices and system architecture

### Architecture style

Use a **modular monolith**: one backend deployment with clear dataset, preprocessing, modelling, prediction, and presentation modules. This gives the project strong boundaries without the operational overhead of microservices.

```text
C-MAPSS files / synthetic fixtures
               |
               v
FastAPI upload and dataset API
               |
               +--> Raw-file store + PostgreSQL audit metadata
               |
               v
Background worker: validate → preprocess → feature engineering
               |                         |
               |                         +--> PostgreSQL experiment/run data
               v
Model training / evaluation jobs → model artifacts + model registry
               |
               v
Prediction, explanation, and maintenance-risk API
               |
               v
Next.js dashboard
```

### Components and rationale

| Component | Technology | Responsibility | Why |
|---|---|---|---|
| Web client | Next.js + TypeScript + shadcn/ui | Dashboard, imports, charts, model comparison, prediction inspection | TypeScript makes API integration safer. Next.js provides a familiar dashboard foundation; shadcn/ui provides accessible, customizable components owned in the repository. |
| API | FastAPI + Pydantic | Dataset, experiment, prediction, and dashboard REST API | FastAPI is type-oriented, fast, and automatically exposes reviewable OpenAPI documentation. It fits the Python ML stack. |
| Metadata/query store | PostgreSQL | Dataset provenance, engine/cycle features, experiments, predictions, evaluations | PostgreSQL is reliable and sufficient for C-MAPSS batch data. It leaves room for a future time-series extension without adding complexity now. |
| ORM/migrations | SQLAlchemy 2.x + Alembic | Persistence and versioned schema changes | Makes the data model reproducible from a clean checkout. |
| Background jobs | Dramatiq + Redis | Preprocessing, training, evaluation, and batch prediction jobs | These activities can be lengthy; workers keep the API responsive with a smaller footprint than a workflow platform. |
| Data processing | Pandas + NumPy | Parsing whitespace-delimited C-MAPSS files and reproducible feature engineering | The dataset is tabular and moderate in size; these are mature, readable tools for it. |
| ML baseline | scikit-learn | Scaling, feature pipelines, and transparent gradient-boosting baseline | A strong tabular baseline establishes measurable value and supports fast iteration before sequence-model complexity. |
| Explainability | SHAP for tree models; feature/contribution summaries for sequence models | Per-prediction drivers | Explanations must connect to individual RUL estimates, not merely global feature rankings. |
| Model artifacts | Local mounted volume initially; S3-compatible abstraction later | Models, preprocessing pipelines, feature manifests, evaluation reports | Keeps local development simple while preserving a credible deployment path. |
| Containers | Docker Compose | Reproducible local stack | Starts the database, Redis, API, worker, and UI using documented commands. |

### Processing model

1. A user imports an FD001 C-MAPSS file with role `train`, `test`, or `test_rul`.
2. The API records the upload and queues validation/preprocessing.
3. The worker parses rows, validates C-MAPSS structure, assigns engine run/cycle records, builds dataset-versioned features, and derives train targets.
4. A training job uses one immutable prepared dataset version, produces a versioned model artifact, and records metrics.
5. A prediction job stores RUL estimates, uncertainty, risk, and explanation payloads. The dashboard reads persisted results.

## 3. Repository and folder structure

```text
TelemetryX/
├── README.md
├── TECHNICAL_SPEC.md
├── .env.example
├── .gitignore
├── compose.yaml
├── docs/
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── cmapss-provenance.md          # source, licence, file checksums, terms
│   └── decisions/                    # architecture decision records (ADRs)
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/                      # HTTP routes and Pydantic contracts
│   │   ├── core/                     # configuration, logging, errors, security boundary
│   │   ├── db/                       # engine, sessions, ORM models
│   │   ├── domains/
│   │   │   ├── datasets/
│   │   │   ├── engines/
│   │   │   ├── experiments/
│   │   │   ├── predictions/
│   │   │   └── recommendations/
│   │   ├── pipelines/                # C-MAPSS parsing, validation, preprocessing, features
│   │   ├── ml/                       # training, inference, evaluation, explainability
│   │   ├── services/
│   │   └── workers/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── contract/
│       └── fixtures/
├── frontend/
│   ├── app/
│   ├── components/                   # includes shadcn/ui primitives
│   ├── lib/
│   ├── types/
│   └── tests/
├── data/
│   ├── raw/                          # ignored downloaded/imported C-MAPSS files
│   ├── processed/                    # ignored feature matrices/sequences
│   └── samples/                      # committed synthetic C-MAPSS-shaped fixtures
├── models/                           # ignored model artifacts; manifests/metrics remain in DB
├── scripts/
│   ├── import_cmapss.py
│   ├── generate_synthetic_cmapss.py
│   ├── train_model.py
│   └── evaluate_model.py
└── infra/
    ├── docker/
    │   ├── backend.Dockerfile
    │   └── frontend.Dockerfile
    └── postgres/init/
```

The existing root `src/`, `app/`, `notebooks/`, and `saved_models/` directories should be deliberately migrated into this layout or removed in a separate cleanup commit when implementation begins. Notebooks may support exploration but cannot be dependencies of the production preprocessing or training pipeline.

## 4. C-MAPSS data contract and schema

### Source dataset decision

NASA C-MAPSS is the sole primary public dataset for this MVP. Its provenance, licence/usage terms, original filenames, source checksums, and import date are documented in `docs/cmapss-provenance.md`. The repository does not commit the full downloaded dataset unless its terms permit it; users import it locally through the documented workflow.

### Canonical C-MAPSS row

C-MAPSS data files are whitespace-delimited and conventionally have no header. Each telemetry row contains 26 ordered values:

```text
unit_number cycle operational_setting_1 operational_setting_2 operational_setting_3
sensor_1 sensor_2 ... sensor_21
```

```json
{
  "dataset_code": "FD001",
  "file_role": "train",
  "unit_number": 1,
  "cycle": 42,
  "operational_settings": [0.0023, 0.0004, 100.0],
  "sensor_values": { "sensor_1": 518.67, "sensor_2": 642.15, "sensor_21": 23.45 }
}
```

`unit_number` identifies an engine only within a dataset version and file role. `cycle` is the ordered operational time axis; it is not converted into calendar timestamps because C-MAPSS does not supply them.

### File roles and target labels

| File role | Purpose | RUL availability |
|---|---|---|
| `train` | Complete run-to-failure sequences used to fit models | Derived per row as `max_cycle_for_unit - cycle`; optional target cap is a declared preprocessing parameter. |
| `test` | Truncated sequences used for final inference/evaluation | Unknown in telemetry rows. |
| `test_rul` | One RUL label for the final cycle of each test unit, in test-unit order | Imported as external ground truth and joined only by explicit dataset/unit-order validation. |

### Validation requirements

- The V1 importer accepts FD001 only; its adapter interface and persisted `dataset_code` retain compatibility with future FD002–FD004 adapters. All imported roles must agree on the subset.
- Telemetry must parse to exactly 26 numeric columns after whitespace normalization; known empty trailing columns are discarded explicitly and reported.
- `unit_number` and `cycle` must be positive integers; cycles must be unique and strictly increasing within a `(dataset_version, file_role, unit_number)` run.
- All 3 operational settings and 21 sensor values must be finite numeric values.
- `test_rul` count must equal the number of unique test units; values must be non-negative numeric RUL labels.
- The import report records accepted rows, rejected rows, missing-cycle warnings, schema version, checksum, and parser version.

### Preprocessing contract

Every prepared dataset records a `preprocessing_version` and immutable parameters:

1. Assign column names and normalize types.
2. Validate unit/cycle sequences and retain raw values unchanged.
3. Identify constant or near-constant sensors from the training split only; record the selected feature list.
4. Scale selected sensor/settings features using statistics fit on training units only.
5. Generate cycle-aware features: normalized cycle, rolling mean/std, lag deltas, slopes, and setting-aware features.
6. Construct capped training RUL labels using the configured cap; the V1 default and initial baseline value is **125 cycles**.
7. Preserve engine-unit splits as part of the prepared feature-set definition so future sequence-model experiments cannot introduce leakage.

No feature fitting, scaling, or sensor selection may use test labels or test-unit information in a way that leaks evaluation information.

## 5. Database schema

All identifiers are UUIDs except the original C-MAPSS unit/cycle numbers. All stored system timestamps are UTC `timestamptz`; `cycle` remains the primary domain ordering field.

| Table | Purpose | Important fields |
|---|---|---|
| `dataset_versions` | Immutable imported/prepared C-MAPSS data lineage | `id`, `dataset_code`, `source_name`, `source_uri`, `checksum_sha256`, `parser_version`, `preprocessing_version`, `parameters`, `status`, timestamps |
| `dataset_files` | Each train/test/test-RUL source file and validation report | `id`, `dataset_version_id`, `file_role`, `original_filename`, `storage_uri`, `checksum_sha256`, counts, `status`, `report`, timestamps |
| `engine_runs` | One engine sequence in one dataset/file role | `id`, `dataset_version_id`, `file_role`, `unit_number`, `max_cycle`, `ground_truth_rul`, `metadata` |
| `engine_cycles` | Raw validated settings and sensor values | `id`, `engine_run_id`, `cycle`, `operational_settings`, `sensor_values`, `quality_flag`, `created_at` |
| `feature_sets` | Versioned prepared feature definition/artifact reference | `id`, `dataset_version_id`, `name`, `feature_version`, `parameters`, `feature_manifest_uri`, timestamps |
| `cycle_features` | Derived features for tabular and sequence models | `id`, `feature_set_id`, `engine_run_id`, `cycle`, `features`, `rul_target`, `sequence_eligible`, timestamps |
| `experiments` | Requested training/evaluation run | `id`, `name`, `dataset_version_id`, `feature_set_id`, `algorithm`, `hyperparameters`, `split_definition`, `random_seed`, `status`, timestamps |
| `model_versions` | Trained immutable model | `id`, `experiment_id`, `version`, `artifact_uri`, `feature_manifest`, `metrics`, `training_data_range`, `status`, timestamps |
| `evaluation_runs` | Results against a named protocol | `id`, `model_version_id`, `dataset_version_id`, `evaluation_role`, `metrics`, `per_unit_results_uri`, timestamps |
| `rul_predictions` | Final-cycle or cycle-level predictions | `id`, `model_version_id`, `engine_run_id`, `cycle`, `predicted_rul`, `lower_bound`, `upper_bound`, `risk_level`, `created_at` |
| `prediction_explanations` | Evidence for one prediction | `id`, `prediction_id`, `method`, `baseline`, `top_contributors`, `summary`, `created_at` |
| `maintenance_recommendations` | Human-readable, non-automated action guidance | `id`, `prediction_id`, `recommendation_type`, `priority`, `rationale`, `status`, timestamps |
| `job_runs` | Asynchronous job state/replay audit | `id`, `job_type`, `idempotency_key`, `entity_id`, `status`, `attempt_count`, `error`, timestamps |

### Constraints and indexes

- `dataset_files` is unique on `(dataset_version_id, file_role, checksum_sha256)`.
- `engine_runs` is unique on `(dataset_version_id, file_role, unit_number)`.
- `engine_cycles` is unique and indexed on `(engine_run_id, cycle)`.
- `cycle_features` is unique on `(feature_set_id, engine_run_id, cycle)`.
- `rul_predictions` is unique on `(model_version_id, engine_run_id, cycle)`.
- `job_runs.idempotency_key` is unique per `job_type`; duplicate requests return the existing job.

Sensor/settings payloads and evolving feature vectors are JSONB. Stable fields used for joins, training provenance, filtering, and ranking stay typed columns. This preserves the fixed C-MAPSS layout while allowing future telemetry adapters.

## 6. REST API design

Base path: `/api/v1`. All endpoints use JSON except multipart file upload. The service publishes OpenAPI 3.1, uses ISO 8601 UTC for system timestamps, and cursor-paginates lists. Authentication is deliberately deferred for this single-user MVP, with a route dependency boundary reserved for future JWT/OIDC.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness/readiness and dependency status. |
| `POST` | `/datasets/imports` | Upload/import a C-MAPSS file with `dataset_code` and `file_role`; returns an async job. |
| `GET` | `/datasets` | List dataset versions, subset, completeness, and processing state. |
| `GET` | `/datasets/{dataset_id}` | Provenance, preprocessing parameters, validation reports, run counts. |
| `GET` | `/datasets/{dataset_id}/engines` | List engine runs; filter by role, risk, RUL range, unit number. |
| `GET` | `/engines/{engine_run_id}` | Run summary, final-cycle prediction, health/degradation state. |
| `GET` | `/engines/{engine_run_id}/cycles` | Cycle telemetry/features for a selected range and fields. |
| `POST` | `/experiments` | Queue reproducible training with dataset, feature set, algorithm, parameters. |
| `GET` | `/experiments/{experiment_id}` | Training state, provenance, parameters, artifacts, results. |
| `GET` | `/models` | List model versions and validation metrics. |
| `POST` | `/models/{model_id}/predictions` | Queue/store batch predictions for a selected dataset role. |
| `GET` | `/predictions` | Filter predictions by dataset, model, risk, RUL, engine. |
| `GET` | `/predictions/{prediction_id}` | Prediction interval, explanation, recommendation. |
| `GET` | `/evaluations` | Compare model evaluations and per-unit errors. |
| `GET` | `/dashboard/summary` | Fleet KPIs, risk distribution, selected model, recommendations. |
| `GET` | `/jobs/{job_id}` | Import/training/prediction job state, errors, retry history. |

```json
POST /api/v1/experiments
{
  "name": "fd001-gradient-boosting-v1",
  "dataset_version_id": "uuid",
  "feature_set_id": "uuid",
  "algorithm": "gradient_boosting_regressor",
  "parameters": { "rul_cap": 125, "random_seed": 42 },
  "split_definition": { "strategy": "group_by_engine", "validation_fraction": 0.2 }
}
```

```json
GET /api/v1/predictions/{prediction_id}
{
  "predicted_rul_cycles": 12.4,
  "prediction_interval_cycles": { "lower": 8.1, "upper": 18.6 },
  "risk_level": "attention",
  "explanation": {
    "summary": "RUL estimate is driven by recent sensor degradation trends.",
    "top_contributors": [{ "feature": "sensor_11_rolling_slope", "direction": "decreases_rul", "magnitude": 0.31 }]
  },
  "recommendation": { "priority": "attention", "action": "Prioritize engineering review within the projected remaining-cycle range." }
}
```

Errors follow an RFC 7807-inspired shape and include a request/job correlation ID. Import validation errors report row-level details where safe to do so.

## 7. Data pipeline

```text
Import → file validation → raw persistence → C-MAPSS parsing → run/cycle validation
       → versioned preprocessing/features → train/evaluate or predict → explain → recommend
```

1. **Import:** accept the source file, compute SHA-256, persist an immutable raw copy, create `dataset_files`, and queue an idempotent job.
2. **Structural validation:** normalize whitespace, discard only known empty trailing fields, verify 26 telemetry columns or one-column test-RUL format, and validate numeric types.
3. **Semantic validation:** verify run/cycle continuity, subset/file-role compatibility, feature completeness, and test/test-RUL unit alignment.
4. **Persistence:** batch-write engine runs/cycles transactionally. A failed dataset cannot be selected for training.
5. **Preparation:** build an immutable feature set from training data only: selected sensors, scalers, rolling features, the configurable capped-RUL policy, and parameters.
6. **Training:** split by engine run, fit only on training runs, train the selected model, and record exact code/data/config provenance.
7. **Evaluation:** evaluate on held-out engine runs or official test/test-RUL pairing; persist aggregate and per-unit errors plus interval calibration.
8. **Inference:** generate final-cycle test predictions and optionally cycle-level trajectories. Persist prediction, interval, explanation, and recommendation.

### Job reliability

Jobs have states `queued`, `running`, `succeeded`, `failed`, and `cancelled`. Transient failures retry with bounded exponential backoff; validation failures do not retry. Every job records attempt count/error/correlation ID and can be manually replayed from an immutable source version.

## 8. RUL modelling, evaluation, and explainability

### Model progression

1. **Naive baseline:** train-derived median/capped RUL, establishing a minimum benchmark.
2. **Tabular baseline:** gradient-boosting regressor using versioned cycle/rolling/degradation features. This is the first production-quality MVP model because it is strong, fast, and explainable.
LSTM, GRU, temporal-convolution, and Transformer models are explicitly deferred to a later comparison phase. They are not part of V1 implementation, dependencies, acceptance criteria, or dashboard claims.

Each model version bundles the estimator, scaler/feature manifest, preprocessing version, dataset version, code revision, hyperparameters, seed, training date, and evaluation metrics. A model cannot score an incompatible feature set.

### RUL targets and leakage controls

- Training-row target: `min(max_cycle_for_train_unit - cycle, rul_cap)`. `rul_cap` is configurable; the V1 baseline uses **125 cycles**.
- Split validation/test data by `unit_number`, never randomly by row or sequence window.
- Fit filtering, imputation, scaling, and feature selection from training partitions only.
- Use official test RUL labels only in evaluation—not preprocessing or prediction.

### Metrics

Every evaluation records RMSE and MAE in cycles; R² only as a supplementary diagnostic; the asymmetric NASA scoring function with its formula/version recorded; per-unit absolute/signed error and error by true-RUL band; plus interval coverage and width when intervals are enabled. Validation and official-test results are always shown separately.

### Explainable predictions

- Tree baseline: SHAP values identify features that increase/decrease an individual RUL estimate, plus global importance.
- Sequence model: expose a documented approximation such as window-level feature sensitivity and label it as non-causal.
- Views show the input window, sensor trajectories, estimate, interval, model/data version, top contributors, and a plain-language summary.
- Explanations describe model evidence, not physical proof of a component fault.

### Risk and maintenance recommendations

Risk derives from the point RUL prediction; its prediction interval remains visible beside the band to show uncertainty. Initial dashboard thresholds are configurable and illustrative only:

| Predicted RUL (cycles) | Dashboard band | Recommended presentation |
|---:|---|---|
| `> 30` | Healthy | Continue monitoring |
| `15 ≤ RUL ≤ 30` | Planning | Plan inspection/maintenance within the projected range |
| `5 ≤ RUL < 15` | Attention | Prioritize engineering review |
| `< 5` | Urgent | Escalate for prompt maintenance review |

The threshold boundaries are applied deterministically as `>30`, `15 ≤ RUL ≤ 30`, `5 ≤ RUL < 15`, and `<5`, so every prediction maps to one band. These thresholds are not real aviation maintenance limits, safety rules, or operational authorization.

Recommendations are review-oriented statements such as “prioritize inspection,” “plan maintenance within the projected cycle range,” or “continue monitoring.” They show uncertainty and state that results are simulated-benchmark analysis, not aircraft dispatch or maintenance authorization.

## 9. Dashboard requirements

| Page | Required capabilities |
|---|---|
| Dataset import | C-MAPSS subset/file-role selection, file guidance, import status, validation report, provenance, completeness. |
| Fleet overview | Engine-run count, final-cycle RUL distribution, risk counts, Attention/Urgent engine ranking, selected-model summary, recent recommendations. |
| Engine detail | Unit/run metadata, settings/sensor trajectories by cycle, degradation trends, RUL trajectory/interval, risk, explanation, recommendation. |
| Model evaluation | Model/version comparison, validation vs official-test metrics, RMSE/MAE/NASA score, residuals, per-unit errors, interval coverage, provenance. |
| Experiment/model registry | Training status, hyperparameters, feature/preprocessing version, artifacts, warnings. |

### Visual and UX requirements

- Treat cycle as the x-axis; never label it as calendar time.
- Plot selected sensor trajectories, rolling/degradation overlays, and clear train/test distinction.
- Plot predicted versus actual RUL only where ground truth is available and label its source.
- Show RUL intervals and risk thresholds directly on prediction charts.
- Support loading, empty, error, and long-running-job states.
- Use shadcn/ui with keyboard access, semantic headings, and WCAG AA contrast. Risk uses text/icons as well as color.

Use TanStack Query for server state, React Hook Form + Zod for forms, and Recharts for charts. They integrate well with TypeScript and limit custom data-fetching/form/chart code.

## 10. Testing and reproducibility strategy

| Layer | Tools | What it verifies |
|---|---|---|
| Backend unit | pytest, pytest-cov | Parsing, target construction, leakage guards, feature calculations, risk mapping, recommendations, explanation formatting. |
| Backend integration | pytest with temporary PostgreSQL/Redis | Migrations, lineage, job state transitions, queries, API/database behavior. |
| API contract | FastAPI TestClient/httpx and OpenAPI snapshot | Request/response shapes, job polling, validation/errors, pagination. |
| ML/data regression | Deterministic fixtures and pinned seeds | Expected RUL/features; baseline reaches a documented fixture threshold and reloads identically. |
| Frontend component | Vitest + React Testing Library | Risk cards, import/explanation content, accessible chart summaries, state handling. |
| End-to-end | Playwright | Import synthetic data → prepare → train baseline → predict → inspect explanation/evaluation. |
| Quality/security | Ruff, mypy, ESLint, Prettier, dependency audit | Style, typing, dependency hygiene, secret prevention. |

Required fixtures include a valid synthetic train/test/test-RUL trio; malformed/mismatched files; known degradation/RUL targets; a deliberately leaky split that must be rejected; and a model/feature-version mismatch that must be rejected.

CI runs linting, unit tests, migration checks, integration tests, frontend tests, and a concise Playwright smoke workflow on each pull request. GitHub Actions is chosen for its transparency and direct repository integration.

## 11. Docker and local development setup

| Service | Image/build | Port | Purpose |
|---|---|---:|---|
| `db` | PostgreSQL official image | 5432 | Dataset, engine/cycle, experiment, prediction, evaluation data. |
| `redis` | Redis official image | 6379 | Dramatiq broker. |
| `api` | `infra/docker/backend.Dockerfile` | 8000 | FastAPI development server. |
| `worker` | same backend image | — | Import, preprocessing, training, evaluation, prediction jobs. |
| `web` | `infra/docker/frontend.Dockerfile` | 3000 | Next.js dashboard. |

Named volumes preserve DB state, raw/processed data, and model artifacts. `.env` is untracked; `.env.example` provides safe values.

```dotenv
POSTGRES_DB=telemetryx
POSTGRES_USER=telemetryx
POSTGRES_PASSWORD=telemetryx_local_only
DATABASE_URL=postgresql+psycopg://telemetryx:telemetryx_local_only@db:5432/telemetryx
REDIS_URL=redis://redis:6379/0
RAW_STORAGE_PATH=/data/raw
PROCESSED_STORAGE_PATH=/data/processed
MODEL_STORAGE_PATH=/models
API_CORS_ORIGINS=http://localhost:3000
MAX_UPLOAD_SIZE_MB=100
```

Use Python 3.12 with `uv` and Node.js 22 LTS with `pnpm`; commit their lockfiles. Use `docker compose` and package scripts rather than a Makefile, which is less convenient for the Windows-first workspace.

### Intended workflow

1. Copy `.env.example` to `.env`.
2. Start the stack with `docker compose up --build`.
3. Apply migrations and load synthetic fixtures.
4. Import local NASA C-MAPSS files with their documented roles.
5. Run a baseline experiment, inspect job status, then run prediction/evaluation.
6. Use the dashboard at `localhost:3000` and API docs at `localhost:8000/docs`.

### Operational requirements

- Structured JSON logs include request ID, job ID, dataset version, experiment/model version, and engine-run ID where relevant.
- `/health` distinguishes liveness from dependency readiness.
- Configure upload size, worker concurrency, retry policy, and allowed CORS origins through environment variables.
- API range queries enforce page/cycle-range limits; large result sets use pagination/downsampling.
- Never commit credentials, raw licensed data, or model binaries. Retain checksums/provenance required for reproducibility.

## 12. Implementation sequence and acceptance criteria

1. **Foundation:** Compose, settings, migrations, structured logging, health endpoint, lint/type/test setup.
2. **Dataset ingestion:** C-MAPSS importer, file/run/cycle schema, validation reports, provenance docs, synthetic fixtures.
3. **Preparation:** versioned RUL targets, no-leak preprocessing, feature sets, engine/cycle query API.
4. **Baseline RUL:** naive and gradient-boosting experiments, registry, persisted predictions, official evaluation workflow.
5. **Explainable risk UX:** SHAP-backed tree explanations, intervals, risk bands, recommendations, fleet/engine dashboards.
6. **Portfolio polish:** screenshots, documentation, CI, accessibility review, reproducibility walkthrough.
7. **Future comparison phase (not V1):** add LSTM/GRU/Transformer models only after establishing a separately approved evaluation plan against the V1 baseline.

### MVP acceptance criteria

- A developer can start the system from a clean checkout using documented Docker instructions.
- Valid C-MAPSS train/test/test-RUL imports produce auditable dataset versions and engine runs.
- Training RUL targets are correct and tests prove no engine-level leakage.
- A baseline model trains reproducibly from a versioned feature set and produces persisted test predictions.
- Evaluation presents RMSE, MAE, the recorded NASA score implementation, and per-unit errors with appropriate labels.
- An engine-detail view shows cycle data, RUL estimate/interval, risk, recommendation, and model evidence.
- UI/docs clearly state results use simulated C-MAPSS data and are not operational aircraft-maintenance advice.

## 13. Approved decisions and remaining design decisions

### Approved decisions

| Decision | Choice |
|---|---|
| Product name | **TelemetryX** |
| Primary public dataset | **NASA C-MAPSS FD001** for V1; adapter/schema reserve a future path for FD002–FD004 |
| Initial domain | Aircraft-engine degradation and RUL estimation using C-MAPSS cycles/settings/sensors |
| Demo/testing data | NASA C-MAPSS locally imported plus committed synthetic C-MAPSS-shaped fixtures |
| Authentication | Deferred for the initial, single-user MVP; preserve future JWT/OIDC boundary |
| Frontend component system | **shadcn/ui** |
| RUL target | Configurable capped RUL; **125 cycles** is the V1 baseline cap |
| ML scope | Explainable gradient-boosting baseline only; sequence models are a later comparison phase |
| Risk bands | Illustrative, configurable RUL bands: Healthy `>30`, Planning `15 ≤ RUL ≤ 30`, Attention `5 ≤ RUL < 15`, Urgent `<5` cycles; never aviation operating limits |
| Initial focus | FD001 ingestion/preprocessing, RUL prediction/evaluation, explainability, risk recommendations, dashboard |

### Remaining decisions before implementation

There are no remaining product or architecture blockers before coding.
