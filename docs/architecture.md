# TelemetryX architecture

Industrial company-scoped operations are implemented in `app.industrial` and `frontend/components/industrial`; see [industrial pilot](industrial-pilot.md). The remaining sections describe the preserved C-MAPSS research subsystem at `/demo`.

The implemented system is a modular monolith: a Next.js dashboard calls FastAPI routes; routes enqueue persisted jobs; services handle dataset preparation, model training and inference. SQLAlchemy stores domain records. Local disk stores exact raw bytes, checksummed feature snapshots and joblib model bundles.

## Request and job boundaries

Mutating long operations return HTTP 202 and a job ID. `/jobs/{id}` exposes queued/running/succeeded/failed/cancelled state, attempts, errors and results. Local development uses one executor thread in one API process. Compose uses a Dramatiq actor and Redis with shared storage. Both execute the same job service. A database update claims a queued job once. Only transient I/O/database failures retry automatically; validation failures remain inspectable. Queued jobs can be cancelled; failed jobs can be explicitly retried.

Local restart recovery marks interrupted jobs failed and redispatches queued jobs. Redis crash recovery is an explicit operator procedure after stopping workers (`python -m app.workers.recover`). Results and service writes are not one distributed transaction; manual replay may create an additional experiment after an interruption. Model training isn't advertised as exactly-once execution.

## Immutable source and feature provenance

A draft is created explicitly, then file roles are appended. A valid role cannot be replaced. Identical imports reuse existing file/run IDs. Preparation seals the version, preventing additions to training/test/label inputs underneath historical experiments. New content requires a new draft. File storage uses content hashes and exact original bytes; dataset identity hashes the role/checksum mapping.

Source preparation saves a full-training reference snapshot. Experiments do not reuse its learned preprocessing. Each experiment first splits raw engine IDs, then fits sensor selection and StandardScaler on training engines only. Held-out engines use transform only. Each experiment writes a separate feature CSV and JSON manifest with snapshot checksum, train/validation engine lists, RUL cap and dataset identity. The model bundle and registry contain matching fitted manifests; prediction rejects mismatches.

Targets are `min(max_cycle - cycle, cap)`. Features use current/past cycles within an engine: settings, selected sensors, cycle/100, rolling means/std, lag differences and finite-difference slopes over 5 and 15 cycles. Slopes are approximations, not least-squares fits. Ground-truth test RUL does not enter training features or inference.

## Estimation, evaluation and explanations

`gradient_boosting` uses HistGradientBoostingRegressor squared-error and 0.05/0.95 quantile models. `naive` uses the median capped training-row RUL with empirical training-target quantiles. Validation covers held-out engine cycles. Test evaluation covers final observed cycles with imported ground-truth labels. NASA score is a sum, so totals across these different sample populations are not directly comparable. RMSE/MAE/R2 and nominal/observed interval coverage and width are persisted separately.

Intervals are nominal prediction intervals, without a calibration guarantee. SHAP TreeExplainer is preferred. Where supported, a model-agnostic SHAP explainer may be used; a local perturbation fallback has its own method label and explicit non-additive/non-causal wording. Constant baseline predictions have no sensor attribution.

Risk derives from the point estimate with illustrative thresholds (>30, 15-30, 5-<15, <5). Intervals remain visible. Recommendations are review-oriented benchmark analysis.

## Presentation and operations

The four tabs live in `frontend/app/page.tsx`. `frontend/lib/api.ts` handles typed JSON/multipart requests and job polling. React state handles selected dataset/model, errors and loading. The last job ID survives a page reload. Fleet aggregation uses test engines in one dataset/model scope; engine details and evaluation plots use the same selection.

SQLite/PostgreSQL selection is explicit and schema upgrades use Alembic. No silent fallback redirects writes to another store. Readiness checks database connectivity. Request IDs and job IDs appear in structured logs. Configured storage paths and upload limits are applied; cycle queries are bounded/paginated. Industrial authentication is separate from the research subsystem. Legacy demo API routes are development-only.
