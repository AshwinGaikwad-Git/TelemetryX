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
  dataset_version_id: string;
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
    interval_metrics?: { nominal_coverage: number; empirical_coverage: number; mean_width: number } | null;
  };
  status: string;
  created_at: string;
}

export interface EvaluationRun {
  dataset_version_id: string;
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
    interval_metrics?: { nominal_coverage: number; empirical_coverage: number; mean_width: number } | null;
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

export interface Job {
  id: string;
  job_type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  attempt_count: number;
  error: string | null;
  result: Record<string, any> | null;
}

export async function waitForJob<T>(job: Job, onProgress?: (job: Job) => void): Promise<T> {
  const started = Date.now();
  while (true) {
    onProgress?.(job);
    if (job.status === "succeeded") return job.result as T;
    if (job.status === "failed" || job.status === "cancelled") {
      const details = job.result?.report?.errors?.join("; ");
      throw new Error(`${details || job.error || job.status} (Job ${job.id})`);
    }
    if (Date.now() - started > 30 * 60 * 1000) {
      throw new Error(`Job ${job.id} is still processing. Refresh to reconnect.`);
    }
    await new Promise((resolve) => setTimeout(resolve, 750));
    job = await request<Job>(`/jobs/${job.id}`);
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
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
  getFleetSummary: (datasetId?: string, modelId?: string) => {
    const params = new URLSearchParams();
    if (datasetId) params.set("dataset_id", datasetId);
    if (modelId) params.set("model_version_id", modelId);
    return request<FleetSummary>(`/dashboard/summary?${params}`);
  },
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  retryJob: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: "POST" }),
  cancelJob: (id: string) => request<Job>(`/jobs/${id}/cancel`, { method: "POST" }),
  createDataset: () => request<{ dataset_id: string }>("/datasets", { method: "POST" }),
  prepareDataset: (id: string) => request<Job>(`/datasets/${id}/prepare`, { method: "POST" }),
  importFile: (datasetId: string, role: string, file: File) => {
    const body = new FormData();
    body.set("dataset_id", datasetId);
    body.set("file_role", role);
    body.set("file", file);
    return request<Job>("/datasets/imports", { method: "POST", body });
  },
  getDatasets: () => request<DatasetVersion[]>("/datasets"),
  getDataset: (id: string) => request<any>(`/datasets/${id}`),
  loadSampleDataset: () =>
    request<Job>("/datasets/sample", {
      method: "POST",
    }),
  getDatasetEngines: (datasetId: string, role?: string, modelId?: string) =>
    request<EngineRunSummary[]>(
      `/datasets/${datasetId}/engines?${new URLSearchParams({ ...(role ? { role } : {}), ...(modelId ? { model_version_id: modelId } : {}) })}`
    ),
  getEngineDetail: (engineRunId: string, modelId?: string) =>
    request<EngineDetail>(`/engines/${engineRunId}${modelId ? `?model_version_id=${modelId}` : ""}`),
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
    request<Job>("/experiments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getModels: () => request<ModelVersion[]>("/models"),
  runPredictions: (modelId: string, datasetId: string, role: string = "test") =>
    request<Job>(
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
