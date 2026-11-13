import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IndustrialWorkspace from "../components/industrial/workspace";
import { Role } from "../lib/industrial-api";

const profile = { id: "user-1", name: "Pilot Manager", email: "manager@example.com", companies: [
  { id: "company-1", name: "Pilot Works", role: "admin" },
  { id: "company-2", name: "Second Company", role: "viewer" },
] };
const machine = { id: "machine-1", site_id: "site-1", asset_tag: "PUMP-001", name: "Cooling pump",
  equipment_type: "Pump", manufacturer: "", model: "", area: "Utilities", criticality: "high",
  operating_state: "running", health: "unknown", connectivity: "not_connected", last_seen: null, notes: "",
  sensors: [{ id: "sensor-1", key: "temperature", name: "Bearing temperature", unit: "degC",
    expected_interval_seconds: 60, warning_low: null, warning_high: 80, persistence_samples: 3,
    freshness: "missing", breach: null, sample_count: 0, latest: null }],
};
const summary = { machine_count: 0, online: 0, attention: 0, unknown: 0, active_alerts: 0,
  open_work_orders: 0, recorded_downtime_minutes: 0, scope: "Selected workspace" };
function response(data: unknown, status = 200) {
  return Promise.resolve({ ok: status < 400, status, json: async () => data });
}
function mockWorkspace({ populated = false, role = "admin" as Role, alert = false } = {}) {
  const fetch = vi.fn((url: string, options?: RequestInit) => {
    const path = new URL(url).pathname;
    if (path.endsWith("/auth/me")) return response({ ...profile, companies: [{ ...profile.companies[0], role }, profile.companies[1]] });
    if (path.endsWith("/auth/logout")) return response(null, 204);
    if (options?.method === "POST" && path.endsWith("/imports")) return response({ accepted: 1, duplicates: 0, rejected: 0, errors: [], checksum_sha256: "source-checksum" });
    if (options?.method === "POST") return response({ id: "created-1" }, 201);
    if (path.includes("company-2")) return response(path.endsWith("/summary") ? summary : []);
    if (path.endsWith("/summary")) return response({ ...summary, machine_count: populated ? 1 : 0, unknown: populated ? 1 : 0 });
    if (path.endsWith("/sites")) return response(populated ? [{ id: "site-1", name: "Pune plant", location: "Pune", timezone: "Asia/Kolkata" }] : []);
    if (path.endsWith("/machines")) return response(populated ? [machine] : []);
    if (path.endsWith("/members")) return response([{ id: profile.id, name: profile.name, email: profile.email, role }]);
    if (path.endsWith("/alerts") && alert) return response([{ id: "alert-1", machine_id: machine.id, sensor_id: "sensor-1", title: "Bearing temperature sustained high limit breach", status: "open", severity: "attention", created_at: "2026-11-13T10:00:00Z", evidence: { value: 90, unit: "degC", warning_high: 80, warning_low: null, consecutive_samples: 3, timestamp: "2026-11-13T10:00:00Z" } }]);
    return response([]);
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());

describe("industrial workspace", () => {
  it("shows account onboarding and keeps the synthetic research demo separate", async () => {
    vi.stubGlobal("fetch", vi.fn(() => response({ detail: "Sign in" }, 401)));
    render(<IndustrialWorkspace />);
    expect(await screen.findByRole("heading", { name: "Build your operating picture." })).toBeInTheDocument();
    expect(screen.getByLabelText("Company name")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open the synthetic C-MAPSS demo/ })).toHaveAttribute("href", "/demo");
  });

  it("starts a company empty and presents a clear registration workflow", async () => {
    mockWorkspace(); render(<IndustrialWorkspace />);
    expect(await screen.findByText("Start with one machine. Build from there.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Register equipment" }));
    expect(screen.getByRole("heading", { name: "Register a site" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add machinery" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register machine" })).toBeDisabled();
  });

  it("resets the view when switching companies and obeys the selected company's role", async () => {
    const fetch = mockWorkspace({ populated: true }); render(<IndustrialWorkspace />);
    expect(await screen.findByRole("button", { name: /Cooling pump/ })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Company workspace"), { target: { value: "company-2" } });
    await waitFor(() => expect(screen.queryByRole("button", { name: /Cooling pump/ })).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Register equipment" })).not.toBeInTheDocument();
    await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.includes("/companies/company-2/machines"))).toBe(true));
  });

  it("does not invent healthy status or predictive results for missing signals", async () => {
    mockWorkspace({ populated: true }); render(<IndustrialWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: /Cooling pump/ }));
    expect(await screen.findByText(/Predictive failure and RUL models are not enabled/)).toBeInTheDocument();
    expect(screen.getByText("No readings for this signal. Upload a CSV or connect your gateway.")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
  });

  it("imports timestamped CSV with session credentials and shows row-level results", async () => {
    const fetch = mockWorkspace({ populated: true }); render(<IndustrialWorkspace />);
    await screen.findByRole("button", { name: /Cooling pump/ });
    fireEvent.click(screen.getByRole("button", { name: "Data connections" }));
    fireEvent.change(screen.getByLabelText("Telemetry CSV"), { target: { files: [new File(["sensor_key,timestamp,value,unit"], "readings.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Validate & import" }));
    expect(await screen.findByText("1 accepted / 0 duplicates / 0 rejected")).toBeInTheDocument();
    const call = fetch.mock.calls.find(([url, options]) => url.endsWith("/machines/machine-1/imports") && options?.method === "POST");
    expect(call?.[1]?.credentials).toBe("include");
    expect(call?.[1]?.body).toBeInstanceOf(FormData);
    expect(call?.[1]?.headers).not.toHaveProperty("Content-Type");
  });

  it("turns an equipment alert into a linked work order", async () => {
    const fetch = mockWorkspace({ populated: true, alert: true }); render(<IndustrialWorkspace />);
    await screen.findByRole("button", { name: /Cooling pump/ });
    fireEvent.click(screen.getByRole("button", { name: "Alert inbox" }));
    fireEvent.click(screen.getByRole("button", { name: "Create inspection work" }));
    fireEvent.click(screen.getByRole("button", { name: "Create work order" }));
    await waitFor(() => expect(fetch.mock.calls.some(([url, options]) => url.endsWith("/work-orders") && options?.method === "POST")).toBe(true));
    const call = fetch.mock.calls.find(([url, options]) => url.endsWith("/work-orders") && options?.method === "POST");
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ alert_id: "alert-1", machine_id: "machine-1" });
  });
});
