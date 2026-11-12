import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "../app/page";

describe("HomePage Dashboard", () => {
  it("renders the primary brand header and NASA badge", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: "TelemetryX", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("C-MAPSS FD001 - synthetic demo available")).toBeInTheDocument();
  });

  it("renders all four navigation tabs", () => {
    render(<HomePage />);
    expect(screen.getByRole("button", { name: /Fleet Overview/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Engine Inspector/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Dataset Explorer/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Model Registry/i })).toBeInTheDocument();
  });

  it("renders fleet risk distribution section on initial overview tab", () => {
    render(<HomePage />);
    expect(screen.getByText(/Fleet Maintenance Risk Distribution/i)).toBeInTheDocument();
    expect(screen.getByText(/Actionable Maintenance Directives/i)).toBeInTheDocument();
  });

  it("allows switching between navigation tabs", async () => {
    render(<HomePage />);

    // Click Dataset Explorer tab
    const datasetTab = screen.getByRole("button", { name: /Dataset Explorer/i });
    fireEvent.click(datasetTab);

    // Expect Dataset Explorer content to be rendered
    await waitFor(() => {
      expect(screen.getByText(/Dataset Lineage & Validation/i)).toBeInTheDocument();
      expect(screen.getByText(/Load Synthetic Demo/i)).toBeInTheDocument();
    });

    // Click Model Registry tab
    const modelsTab = screen.getByRole("button", { name: /Model Registry/i });
    fireEvent.click(modelsTab);

    // Expect Model Registry content
    await waitFor(() => {
      expect(screen.getByText(/Model Registry & Benchmark Evaluation/i)).toBeInTheDocument();
      expect(screen.getByText(/Official NASA Score/i)).toBeInTheDocument();
    });
  });
});


