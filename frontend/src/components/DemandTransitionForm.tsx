import { useState } from "react";
import type { DemandState, DemandTransitionCommand, DemandRecord } from "../types";

interface DemandTransitionFormProps {
  onSubmit: (demandId: string, command: DemandTransitionCommand) => Promise<DemandRecord>;
}

/** Collect and submit an accessible optimistic-locking demand transition. */
export function DemandTransitionForm({ onSubmit }: DemandTransitionFormProps): React.JSX.Element {
  const [demandId, setDemandId] = useState("DEM-READINESS-01");
  const [destination, setDestination] = useState<DemandState>("triaged");
  const [expectedVersion, setExpectedVersion] = useState(0);
  const [resolutionNote, setResolutionNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DemandRecord | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!demandId.trim()) {
      setError("A demand ID is required.");
      return;
    }
    if (["completed", "cancelled"].includes(destination) && !resolutionNote.trim()) {
      setError("A resolution note is required for completed or cancelled demands.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const transitioned = await onSubmit(demandId.trim(), {
        destination,
        expected_version: expectedVersion,
        resolution_note: resolutionNote
      });
      setResult(transitioned);
      setExpectedVersion(transitioned.version);
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "The demand could not be transitioned."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="demand-transition-title">
      <p className="section-label">DEMAND WORKFLOW</p>
      <h2 id="demand-transition-title">Transition demand</h2>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="demand-id">Demand ID</label>
        <input
          id="demand-id"
          value={demandId}
          onChange={(event) => setDemandId(event.target.value)}
          aria-required="true"
        />
        <label htmlFor="demand-destination">Destination</label>
        <select
          id="demand-destination"
          value={destination}
          onChange={(event) => setDestination(event.target.value as DemandState)}
        >
          <option value="triaged">Triaged</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <label htmlFor="demand-version">Expected version</label>
        <input
          id="demand-version"
          type="number"
          min="0"
          value={expectedVersion}
          onChange={(event) => setExpectedVersion(Number(event.target.value))}
          aria-required="true"
        />
        <label htmlFor="resolution-note">Resolution note</label>
        <textarea
          id="resolution-note"
          value={resolutionNote}
          onChange={(event) => setResolutionNote(event.target.value)}
        />
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        {result ? (
          <p className="success-notice" aria-live="polite">
            {result.demand_id} is {result.state.replace("_", " ")} at version {result.version}.
          </p>
        ) : null}
        <button type="submit" disabled={loading}>
          {loading ? "Transitioning…" : "Transition demand"}
        </button>
      </form>
    </section>
  );
}