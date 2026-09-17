import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { DemandRecord } from "../types";
import { DemandTransitionForm } from "./DemandTransitionForm";

const transitionedDemand: DemandRecord = {
  demand_id: "DEM-READINESS-01",
  state: "triaged",
  version: 1,
  resolution_note: null,
  history: [],
  updated_at: "2026-09-17T10:00:00Z"
};

describe("DemandTransitionForm", () => {
  it("submits a transition and renders the persisted result", async () => {
    const onSubmit = vi.fn().mockResolvedValue(transitionedDemand);
    const user = userEvent.setup();
    render(<DemandTransitionForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Transition demand" }));

    expect(onSubmit).toHaveBeenCalledWith("DEM-READINESS-01", {
      destination: "triaged",
      expected_version: 0,
      resolution_note: ""
    });
    expect(await screen.findByText("DEM-READINESS-01 is triaged at version 1.")).toBeInTheDocument();
  });

  it("blocks a terminal transition with no resolution note", async () => {
    const onSubmit = vi.fn().mockResolvedValue(transitionedDemand);
    const user = userEvent.setup();
    render(<DemandTransitionForm onSubmit={onSubmit} />);

    await user.selectOptions(screen.getByLabelText("Destination"), "completed");
    await user.click(screen.getByRole("button", { name: "Transition demand" }));

    expect(screen.getByRole("alert")).toHaveTextContent("resolution note is required");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("shows loading and backend failure states", async () => {
    let rejectSubmission: (reason: Error) => void = () => undefined;
    const onSubmit = vi.fn().mockReturnValue(new Promise<DemandRecord>((_, reject) => {
      rejectSubmission = reject;
    }));
    const user = userEvent.setup();
    render(<DemandTransitionForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Transition demand" }));
    expect(screen.getByRole("button", { name: "Transitioning…" })).toBeDisabled();

    rejectSubmission(new Error("Transition conflict"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Transition conflict");
  });
});