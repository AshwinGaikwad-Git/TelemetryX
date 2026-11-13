export type Role = "admin" | "manager" | "engineer" | "technician" | "viewer";
export interface Workspace { id: string; name: string; role: Role }
export interface Profile { id: string; name: string; email: string; companies: Workspace[] }
export interface Site { id: string; name: string; location: string; timezone: string }
export interface Sensor {
  id: string; key: string; name: string; unit: string;
  expected_interval_seconds: number; warning_low: number | null; warning_high: number | null;
  persistence_samples: number; freshness: string; breach: string | null; sample_count: number;
  latest: { value: number; timestamp: string } | null;
}
export interface Machine {
  id: string; site_id: string; asset_tag: string; name: string; equipment_type: string;
  manufacturer: string; model: string; area: string; criticality: string; operating_state: string;
  health: string; connectivity: string; last_seen: string | null; notes: string; sensors: Sensor[];
}
export interface Summary {
  machine_count: number; online: number; attention: number; unknown: number;
  active_alerts: number; open_work_orders: number; recorded_downtime_minutes: number; scope: string;
}
export interface Alert {
  id: string; machine_id: string; sensor_id: string; title: string; status: string;
  severity: string; created_at: string; evidence: {
    value: number; unit: string; warning_high: number | null; warning_low: number | null;
    consecutive_samples: number; timestamp: string;
  };
}
export interface WorkOrder {
  id: string; machine_id: string; alert_id: string | null; title: string; description: string;
  status: string; priority: string; assigned_to: string | null; due_at: string | null;
  findings: string; component: string; downtime_minutes: number; created_at: string;
}
export interface TeamMember { id: string; name: string; email: string; role: Role }
export interface Audit { id: string; actor: string; action: string; entity_id: string; created_at: string }
export interface IngestionKey { id: string; name: string; active: boolean; created_at: string }
export interface ImportReport {
  accepted: number; duplicates: number; rejected: number; checksum_sha256: string;
  errors: { row: number; error: string }[];
}
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function industrialRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/industrial${path}`, {
      ...options, credentials: "include",
      headers: { ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...options.headers },
    });
  } catch {
    throw new ApiError(503, "Cannot reach TelemetryX. Check that the website and backend are running, then try again.");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const message = typeof payload.detail === "string" ? payload.detail :
      Array.isArray(payload.detail) ? payload.detail.map((e: { loc: string[]; msg: string }) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ") : response.status >= 500 ? "The TelemetryX backend is unavailable. Please restart it and try again." : "Request failed";
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? undefined as T : response.json();
}
export const post = <T,>(path: string, payload?: unknown) => industrialRequest<T>(path, {
  method: "POST", ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
});
export const patch = <T,>(path: string, payload: unknown) => industrialRequest<T>(path, {
  method: "PATCH", body: JSON.stringify(payload),
});
