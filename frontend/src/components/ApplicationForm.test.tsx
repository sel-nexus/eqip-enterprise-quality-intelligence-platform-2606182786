import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationForm } from "./ApplicationForm";

describe("ApplicationForm", () => {
  it("submits trimmed, comma-separated application data", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ApplicationForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/Application name/), " Claims Portal ");
    await user.type(screen.getByLabelText(/Product/), " Claims ");
    await user.type(screen.getByLabelText(/Owners/), " u-42, u-64 ");
    await user.clear(screen.getByLabelText(/Technology/));
    await user.type(screen.getByLabelText(/Technology/), " React, FastAPI ");
    await user.click(screen.getByRole("button", { name: "Register application" }));

    expect(onSubmit).toHaveBeenCalledWith({
      name: "Claims Portal",
      segment_id: "SEG-HEALTH",
      product: "Claims",
      criticality: "high",
      tier: "tier-1",
      owners: ["u-42", "u-64"],
      technology: ["React", "FastAPI"],
      health: "amber",
      expected_version: 0
    });
    expect(screen.getByLabelText(/Application name/)).toHaveValue("");
  });

  it("shows validation and makes no request for incomplete input", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<ApplicationForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Register application" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Name, product, at least one owner");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables submission while the request is pending and exposes a failure", async () => {
    let rejectSubmission: (reason: Error) => void = () => undefined;
    const onSubmit = vi.fn().mockReturnValue(new Promise<void>((_, reject) => {
      rejectSubmission = reject;
    }));
    const user = userEvent.setup();
    render(<ApplicationForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/Application name/), "Claims Portal");
    await user.type(screen.getByLabelText(/Product/), "Claims");
    await user.type(screen.getByLabelText(/Owners/), "u-42");
    await user.click(screen.getByRole("button", { name: "Register application" }));

    expect(screen.getByRole("button", { name: "Registering…" })).toBeDisabled();
    rejectSubmission(new Error("Portfolio unavailable"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Portfolio unavailable");
  });
});