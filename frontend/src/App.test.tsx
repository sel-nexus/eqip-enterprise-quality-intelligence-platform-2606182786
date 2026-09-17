import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import App from "./App";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

/** Verify dashboard interactions against typed same-origin API responses. */
describe("App", () => {
  it("submits a governed application and displays its persisted business id", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { items: [], total: 0 }, correlation_id: "c-list" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { application_id: "APP-000184", name: "Claims Portal", segment_id: "SEG-HEALTH", product: "Claims", criticality: "high", tier: "tier-1", owners: ["u-42"], technology: ["React", "FastAPI"], health: "amber", lifecycle: "active", version: 1, created_at: "2026-09-17T10:00:00Z", updated_at: "2026-09-17T10:00:00Z" }, correlation_id: "c-create" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("No governed applications are recorded yet.");
    await user.type(screen.getByLabelText(/Application name/), "Claims Portal");
    await user.type(screen.getByLabelText(/Product/), "Claims");
    await user.type(screen.getByLabelText(/Owners/), "u-42");
    await user.click(screen.getByRole("button", { name: "Register application" }));
    expect(await screen.findByText("APP-000184")).toBeInTheDocument();
    expect(screen.getByText(/APP-000184 is active/)).toBeInTheDocument();
  });

  it("transitions a demand and renders a persisted blocked readiness result", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { items: [], total: 0 }, correlation_id: "c-list" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { demand_id: "DEM-READINESS-01", state: "triaged", version: 1, resolution_note: null, history: [], updated_at: "2026-09-17T10:00:00Z" }, correlation_id: "c-demand" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ data: { release_id: "REL-READINESS-01", version: 1, inputs: { expected_version: 0, applicable_gate_count: 4, passed_gate_count: 4, unwaived_gate_failures: 0, test_pass_rate: 95, open_defect_count: 1, critical_defect_count: 0, automation_coverage: 80 }, weights: { gates: 0.4, tests: 0.3, defects: 0.15, automation: 0.15 }, score: 90.75, recommendation: "Blocked", timestamp: "2026-09-17T10:00:00Z" }, correlation_id: "c-readiness" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("No governed applications are recorded yet.");
    await user.click(screen.getByRole("button", { name: "Transition demand" }));
    expect(await screen.findByText(/DEM-READINESS-01 is triaged/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calculate readiness" }));
    expect(await screen.findByText((_, element) => element?.className === "readiness-result" && element.textContent?.includes("Blocked — weighted score 90.75%") === true)).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.className === "readiness-result" && element.textContent?.includes("Gates 40% · Tests 30%") === true)).toBeInTheDocument();
  });

  it("requires a terminal demand resolution note before making a request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { items: [], total: 0 }, correlation_id: "c-list" }), { status: 200 })));
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("No governed applications are recorded yet.");
    await user.selectOptions(screen.getByLabelText("Destination"), "cancelled");
    await user.click(screen.getByRole("button", { name: "Transition demand" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("resolution note is required");
  });

  it("shows a retryable collection error when the API cannot load", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Portfolio unavailable" }), { status: 503 })));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Portfolio unavailable");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("reports missing required form values before making a create request", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ data: { items: [], total: 0 }, correlation_id: "c-list" }), { status: 200 })));
    render(<App />);
    await screen.findByText("No governed applications are recorded yet.");
    fireEvent.click(screen.getByRole("button", { name: "Register application" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Name, product"));
  });
});
