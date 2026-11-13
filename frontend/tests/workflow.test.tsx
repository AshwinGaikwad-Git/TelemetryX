import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "../app/demo/page";
import { api, Job, waitForJob } from "../lib/api";

const dataset = {
  id: "dataset-1", dataset_code: "FD001", source_name: "Synthetic fixtures",
  status: "prepared", train_count: 5, test_count: 2, has_test_rul: true,
  engine_count: 7, created_at: "2026-11-13", updated_at: "2026-11-13", files: [],
};
const summary = {
  fleet_size: 0, mean_predicted_rul: 0, attention_required_count: 0,
  risk_distribution: { healthy: 0, planning: 0, attention: 0, urgent: 0 },
  active_model: null, critical_engines: [], latest_recommendations: [],
};
function job(id: string, result: Record<string, any> = {}): Job {
  return { id, job_type: id, status: "succeeded", attempt_count: 1, result, error: null };
}
function response(data: unknown) {
  return Promise.resolve({ ok: true, json: async () => data });
}

beforeEach(() => window.localStorage.clear());
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("background workflow", () => {
  it("polls queued jobs until their result is available", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn().mockImplementationOnce(() => response({ ...job("poll"), status: "running" }))
      .mockImplementationOnce(() => response(job("poll", { dataset_id: "ready" })));
    vi.stubGlobal("fetch", fetch);
    const progress = vi.fn();
    const completed = waitForJob({ ...job("poll"), status: "queued" }, progress);
    await vi.advanceTimersByTimeAsync(1500);
    expect(await completed).toEqual({ dataset_id: "ready" });
    expect(progress.mock.calls.map(([value]) => value.status)).toEqual(["queued", "running", "succeeded"]);
  });

  it("surfaces validation details instead of treating failed imports as successful", async () => {
    await expect(waitForJob({ ...job("bad"), status: "failed", result: {
      report: { errors: ["Expected 26 columns"] },
    } })).rejects.toThrow("Expected 26 columns (Job bad)");
  });

  it("lets the browser set the multipart boundary for custom file imports", async () => {
    const fetch = vi.fn((_url: string, _options?: RequestInit) => response(job("upload")));
    vi.stubGlobal("fetch", fetch);
    await api.importFile("dataset-1", "train", new File(["raw"], "train.txt"));
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.headers).not.toHaveProperty("Content-Type");
  });

  it("completes the demo through job results and scopes its refresh to the resulting model", async () => {
    let loaded = false;
    const fetch = vi.fn((input: string) => {
      const url = new URL(input);
      if (url.pathname.endsWith("/datasets/sample")) {
        loaded = true;
        return response(job("sample", { dataset_id: dataset.id }));
      }
      if (url.pathname.endsWith("/experiments")) return response(job("train", { model_version_id: "model-1" }));
      if (url.pathname.endsWith("/predictions")) return response(job("predict"));
      if (url.pathname.endsWith("/summary")) return response(summary);
      if (url.pathname.endsWith("/datasets")) return response(loaded ? [dataset] : []);
      if (url.pathname.endsWith("/dataset-1")) return response(dataset);
      return response([]);
    });
    vi.stubGlobal("fetch", fetch);
    render(<HomePage />);
    fireEvent.click(screen.getByRole("button", { name: "Quick Demo Setup" }));
    await waitFor(() => expect(screen.getByText(/Synthetic demo completed/)).toBeInTheDocument());
    expect(fetch.mock.calls.some(([url]) => url.includes("dataset_id=dataset-1&model_version_id=model-1"))).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("succeeded");
  });

  it("shows failed refreshes and exposes a custom-file upload form", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("API offline"))));
    render(<HomePage />);
    await waitFor(() => expect(screen.getByText(/Could not refresh dashboard: API offline/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Dataset Explorer/ }));
    expect(screen.getByLabelText("C-MAPSS file")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload file" })).toBeDisabled();
  });
});
