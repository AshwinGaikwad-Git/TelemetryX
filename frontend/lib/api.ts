/**
 * TelemetryX API Client
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export interface DatasetVersion {
  id: string;
  dataset_code: string;
  source_name: string;
  status: string;
  engine_count: number;
  train_count: number;
  test_count: number;
  has_test_rul: boolean;
  created_at: string;
  updated_at: string;
}

export interface EngineRunSummary {
  id: string;
  dataset_version_id: string;
  file_role: string;
  unit_number: number;
  max_cycle: number;
  ground_truth_rul: number | null;
  predicted_rul: number | null;
  risk_level: "healthy" | "planning" | "attention" | "urgent" | null;
  created_at: string;
}

export interface EngineDetail extends EngineRunSummary {
  prediction: {
    id: string;
    predicted_rul: number;
    lower_bound: number;
    upper_bound: number;
    risk_level: "healthy" | "planning" | "attention" | "urgent";
    cycle: number;
  } | null;
  explanation: {
    method: string;
    baseline: { expected_value: number } | null;
    top_contributors: Array<{
      feature: string;
      description: string;
      attribution: number;
      magnitude: number;
      direction: "increases_rul" | "decreases_rul";
    }>;
    summary: string;
  } | null;
  recommendation: {
    recommendation_type: string;
    priority: "healthy" | "planning" | "attention" | "urgent";
    rationale: string;
    status: string;
  } | null;
}

export interface EngineCycleData {
  cycle: number;
  operational_settings: number[];
  sensor_values: Record<string, number>;
}

export interface FleetSummary {
  fleet_size: number;
  mean_predicted_rul: number;
  risk_distribution: {
    healthy: number;
    planning: number;
    attention: number;
    urgent: number;
  };
  attention_required_count: number;
  active_model: {
    id: string;
    version: string;
    metrics: Record<string, any>;
    status: string;
  } | null;
  critical_engines: Array<{
    engine_run_id: string;
    unit_number: number;
    cycle: number;
    predicted_rul: number;
    lower_bound: number;
    upper_bound: number;
    risk_level: string;
    recommendation: string | null;
  }>;
  latest_recommendations: Array<{
    unit_number: number;
    priority: string;
    type: string;
    rationale: string;
  }>;
}

export interface ModelVersion {
  id: string;
  experiment_id: string;
  version: string;
  artifact_uri: string;
  metrics: {
    rmse: number;
    mae: number;
    r2: number;
    nasa_score: number;
    sample_size: number;
  };
  status: string;
  created_at: string;
}

export interface EvaluationRun {
  id: string;
  model_version_id: string;
  model_version: string;
  evaluation_role: string;
  metrics: {
    rmse: number;
    mae: number;
    r2: number;
    nasa_score: number;
    sample_size: number;
    per_unit_results?: Array<{
      unit_number: number;
      actual_rul: number;
      predicted_rul: number;
      error: number;
      abs_error: number;
      nasa_penalty: number;
    }>;
  };
  created_at: string;
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`API Error [${res.status}]: ${errorText || res.statusText}`);
  }

  return res.json();
}

export const api = {
  getFleetSummary: () => request<FleetSummary>("/dashboard/summary"),
  getDatasets: () => request<DatasetVersion[]>("/datasets"),
  getDataset: (id: string) => request<any>(`/datasets/${id}`),
  loadSampleDataset: () =>
    request<{ dataset_id: string; reports: any }>("/datasets/sample", {
      method: "POST",
    }),
  getDatasetEngines: (datasetId: string, role?: string) =>
    request<EngineRunSummary[]>(
      `/datasets/${datasetId}/engines${role ? `?role=${role}` : ""}`
    ),
  getEngineDetail: (engineRunId: string) =>
    request<EngineDetail>(`/engines/${engineRunId}`),
  getEngineCycles: (engineRunId: string, start?: number, end?: number) =>
    request<EngineCycleData[]>(
      `/engines/${engineRunId}/cycles?start_cycle=${start || 1}${end ? `&end_cycle=${end}` : ""}`
    ),
  getExperiments: () => request<any[]>("/experiments"),
  runExperiment: (payload: {
    dataset_version_id: string;
    name?: string;
    algorithm?: string;
    hyperparameters?: any;
    rul_cap?: number;
    validation_fraction?: number;
  }) =>
    request<{
      experiment_id: string;
      model_version_id: string;
      version: string;
      metrics: any;
      status: string;
    }>("/experiments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getModels: () => request<ModelVersion[]>("/models"),
  runPredictions: (modelId: string, datasetId: string, role: string = "test") =>
    request<any[]>(
      `/models/${modelId}/predictions?dataset_id=${datasetId}&role=${role}`,
      { method: "POST" }
    ),
  getPredictions: (modelId?: string, riskLevel?: string) => {
    const params = new URLSearchParams();
    if (modelId) params.append("model_version_id", modelId);
    if (riskLevel) params.append("risk_level", riskLevel);
    const qs = params.toString();
    return request<any[]>(`/predictions${qs ? `?${qs}` : ""}`);
  },
  getPrediction: (id: string) => request<any>(`/predictions/${id}`),
  getEvaluations: () => request<EvaluationRun[]>("/evaluations"),
};
