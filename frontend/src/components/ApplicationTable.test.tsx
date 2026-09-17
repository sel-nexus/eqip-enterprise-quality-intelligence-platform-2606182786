import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ApplicationRecord } from "../types";
import { ApplicationTable } from "./ApplicationTable";

const application: ApplicationRecord = {
  application_id: "APP-000184",
  name: "Claims Portal",
  segment_id: "SEG-HEALTH",
  product: "Claims",
  criticality: "high",
  tier: "tier-1",
  owners: ["u-42"],
  technology: ["React"],
  health: "amber",
  lifecycle: "active",
  version: 1,
  created_at: "2026-09-17T10:00:00Z",
  updated_at: "2026-09-17T10:00:00Z"
};

describe("ApplicationTable", () => {
  it("renders persisted application business data", () => {
    render(<ApplicationTable applications={[application]} loading={false} error={null} onRetry={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Governed applications" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "APP-000184" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("amber");
  });

  it("renders loading and empty collection states", () => {
    const { rerender } = render(<ApplicationTable applications={[]} loading error={null} onRetry={vi.fn()} />);
    expect(screen.getByText("Loading governed applications…")).toBeInTheDocument();

    rerender(<ApplicationTable applications={[]} loading={false} error={null} onRetry={vi.fn()} />);
    expect(screen.getByText("No governed applications are recorded yet.")).toBeInTheDocument();
  });

  it("renders an error and retries on request", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(<ApplicationTable applications={[]} loading={false} error="Portfolio unavailable" onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Portfolio unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});