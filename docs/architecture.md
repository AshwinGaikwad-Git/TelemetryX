# TelemetryX Architecture

## 1. System Overview
TelemetryX is a predictive-maintenance system designed to ingest, process, evaluate, explain, and monitor Remaining Useful Life (RUL) for turbofan engines using NASA C-MAPSS simulation data.

The system is architected as a **modular monolith** with clean boundary layers between data ingestion, tabular feature pipelines, ML model training & registry, risk scoring & explainability, and the Next.js presentation tier.

```text
┌────────────────────────────────────────────────────────┐
│                   Next.js Frontend                     │
│  - Fleet Overview & KPI Cards                          │
│  - Engine Telemetry & Degradation Visualizer           │
│  - Model Registry & Evaluation Dashboard               │
│  - SHAP Attribution & Maintenance Recommendations     │
└───────────────────────────┬────────────────────────────┘
                            │ REST / JSON (OpenAPI)
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│  - /api/v1/datasets: Ingestion, validation, lineage   │
│  - /api/v1/engines: Runs, cycles, sensor series        │
│  - /api/v1/experiments: Model training configuration   │
│  - /api/v1/models: Model artifacts, metrics, inference │
│  - /api/v1/predictions: Explanations, risk bounds      │
│  - /api/v1/dashboard: Fleet KPIs, risk aggregates      │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
┌─────────────▼─────────────┐ ┌────────────▼─────────────┐
│    PostgreSQL / SQLite    │ │       Local Storage       │
│  - Lineage & metadata     │ │  - Raw source files       │
│  - Engine cycles & runs   │ │  - Feature matrices       │
│  - Models, metrics, SHAP  │ │  - Joblib model bundles   │
└───────────────────────────┘ └──────────────────────────┘
```

## 2. Key Modules & Boundaries

1. **`app.pipelines`**:
   - `parser.py`: Whitespace-delimited format parsing and row normalization.
   - `validator.py`: Structural (column counts, numeric bounds) and semantic (monotonic cycles, unit matching) integrity checks.
   - `preprocessor.py`: Sensor selection, rolling aggregates (mean, std, lag delta, slope), cycle normalization.
   - `features.py`: Zero-leakage feature matrix construction and capped RUL derivation ($RUL_{cap} = 125$).

2. **`app.ml`**:
   - `models.py`: Naive baseline estimator and HistGradientBoostingRegressor / GradientBoostingRegressor.
   - `evaluator.py`: Official NASA scoring function ($S$), RMSE, MAE, R², error distributions.
   - `explainability.py`: TreeSHAP attribution and top positive/negative sensor contributors.
   - `risk.py`: Categorical risk levels (`Healthy`, `Planning`, `Attention`, `Urgent`) and actionable maintenance recommendations.

3. **`app.db`**:
   - Versioned schema for datasets, files, engine runs, telemetry cycles, feature sets, experiments, models, predictions, explanations, and job runs.

4. **`app.api.routes`**:
   - Strongly-typed Pydantic contracts and async REST handlers.

5. **`app.workers`**:
   - Asynchronous job execution for file processing, model fitting, and batch predictions.

## 3. Data Flow & Leakage Prevention Guarantees
- **Strict Engine-Level Splitting:** Splits are assigned strictly by `unit_number` groups. Rows from the same engine never span across train and validation sets.
- **Fit-on-Train Scalers:** Scalers (e.g. StandardScaler) and sensor variance filters are fit strictly on training engine runs. Test data is transformed using fitted parameters only.
- **RUL Ground Truth Separation:** Test set RUL labels (`RUL_FD001.txt`) are isolated from feature engineering and inference, and only joined during formal evaluation reporting.
