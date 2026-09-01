import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "../app/page";

describe("HomePage", () => {
  it("renders the foundation smoke view", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: "TelemetryX" })).toBeInTheDocument();
  });
});
