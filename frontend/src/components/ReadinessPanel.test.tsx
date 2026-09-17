import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ReadinessSnapshot } from "../types";
import { ReadinessPanel } from "./ReadinessPanel";

const snapshot: ReadinessSnapshot = {
  release_id: "REL-READINESS-01",
  version: 1,
  inputs: {
    expected_version: 0,
    applicable_gate_count: 4,
    passed_gate_count: 4,
    unwaived_gate_failures: 0,
    test_pass_rate: 95,
    open_defect_count: 1,
    critical_defect_count: 0,
    automation_coverage: 80
  },
  weights: { gates: 0.4, tests: 0.3, defects: 0.15, automation: 0.15 },
  score: 90.75,
  recommendation: "Conditional",
  timestamp: "2026-09-17T10:00:00Z"
};

describe("ReadinessPanel", () => {
  it("submits evidence and renders the persisted weighted decision", async () => {
    const onSubmit = vi.fn().mockResolvedValue(snapshot);
    const user = userEvent.setup();
    render(<ReadinessPanel onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Calculate readiness" }));

    expect(onSubmit).toHaveBeenCalledWith("REL-READINESS-01", snapshot.inputs);
    const result = await screen.findByText((_, element) => (
      element?.className === "readiness-result"
      && element.textContent?.includes("Conditional — weighted score 90.75%") === true
    ));
    expect(result).toHaveTextContent("Gates 40% · Tests 30% · Defects 15% · Automation 15%");
  });

  it("requires a release ID before requesting readiness", async () => {
    const onSubmit = vi.fn().mockResolvedValue(snapshot);
    const user = userEvent.setup();
    render(<ReadinessPanel onSubmit={onSubmit} />);

    await user.clear(screen.getByLabelText("Release ID"));
    await user.click(screen.getByRole("button", { name: "Calculate readiness" }));

    expect(screen.getByRole("alert")).toHaveTextContent("A release ID is required.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows loading and failure feedback for a rejected calculation", async () => {
    let rejectSubmission: (reason: Error) => void = () => undefined;
    const onSubmit = vi.fn().mockReturnValue(new Promise<ReadinessSnapshot>((_, reject) => {
      rejectSubmission = reject;
    }));
    const user = userEvent.setup();
    render(<ReadinessPanel onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Calculate readiness" }));
    expect(screen.getByRole("button", { name: "Calculating…" })).toBeDisabled();

    rejectSubmission(new Error("Readiness unavailable"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Readiness unavailable");
  });
});