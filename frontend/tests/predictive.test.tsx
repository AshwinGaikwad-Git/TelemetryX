import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Predictive from "../components/industrial/predictive";
import { Machine } from "../lib/industrial-api";

const machine: Machine = { id: "machine-1", site_id: "site-1", asset_tag: "PUMP-1", name: "Pump", equipment_type: "Pump", manufacturer: "", model: "", area: "", criticality: "medium", operating_state: "running", health: "unknown", connectivity: "online", last_seen: null, notes: "", sensors: [{ id: "s1", key: "temperature", name: "Temperature", unit: "degC", expected_interval_seconds: 60, warning_low: null, warning_high: 90, persistence_samples: 3, freshness: "fresh", breach: null, sample_count: 3, latest: { value: 55, timestamp: "2026-11-13T10:00:00Z" } }] };
const model = { id: "model-1", checksum: "checksum", created_at: "2026-11-13T10:00:00Z", feature_schema: { temperature: { unit: "degC" } }, metrics: { mae_hours: 5, rmse_hours: 6, baseline_mae_hours: 20, interval_coverage: .85, training_runs: 4, validation_runs: 1, training_rows: 120, validation_rows: 30 } };
function mock(status: unknown) {
  const fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => status }));
  vi.stubGlobal("fetch", fetch); return fetch;
}
afterEach(() => vi.unstubAllGlobals());
describe("equipment predictions", () => {
  it("shows missing model readiness and uploads labeled history to the selected machine", async () => {
    const fetch = mock({ model: null, ready: false, reason: "Train an equipment-specific model first.", history: [] });
    render(<Predictive base="/companies/c1" machine={machine} canConfigure canEdit />);
    expect(await screen.findByText("Train an equipment-specific model first.")).toBeInTheDocument();
    expect(screen.queryByText(/estimated remaining life/)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Labeled training history"), { target: { files: [new File(["run_id,remaining_hours,temperature"], "training.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Train equipment model" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/machines/machine-1/predictive/train", expect.objectContaining({ method: "POST", body: expect.any(FormData), credentials: "include" })));
  });
  it("blocks estimates for stale inputs and respects viewer permissions", async () => {
    mock({ model, ready: false, reason: "Fresh readings required for temperature.", history: [] });
    const view = render(<Predictive base="/companies/c1" machine={machine} canConfigure canEdit />);
    expect(await screen.findByRole("button", { name: "Estimate remaining life" })).toBeDisabled();
    view.rerender(<Predictive base="/companies/c1" machine={machine} canConfigure={false} canEdit={false} />);
    expect(screen.queryByRole("button", { name: "Estimate remaining life" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Labeled training history")).not.toBeInTheDocument();
  });
  it("runs compatible inference and displays held-out metrics", async () => {
    const fetch = mock({ model, ready: true, reason: null, history: [] });
    render(<Predictive base="/companies/c1" machine={machine} canConfigure canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: "Estimate remaining life" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/machines/machine-1/predictive/predict", expect.objectContaining({ method: "POST", credentials: "include" })));
    expect(screen.getByText("85.0%")).toBeInTheDocument();
    expect(screen.getByText(/separate runs/)).toBeInTheDocument();
  });
});
