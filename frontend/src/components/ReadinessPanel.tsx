import { useState } from "react";
import type { ReadinessCommand, ReadinessSnapshot } from "../types";

interface ReadinessPanelProps {
  onSubmit: (releaseId: string, command: ReadinessCommand) => Promise<ReadinessSnapshot>;
}

/** Capture release evidence and render the persisted weighted readiness decision. */
export function ReadinessPanel({ onSubmit }: ReadinessPanelProps): React.JSX.Element {
  const [releaseId, setReleaseId] = useState("REL-READINESS-01");
  const [values, setValues] = useState<ReadinessCommand>({
    expected_version: 0,
    applicable_gate_count: 4,
    passed_gate_count: 4,
    unwaived_gate_failures: 0,
    test_pass_rate: 95,
    open_defect_count: 1,
    critical_defect_count: 0,
    automation_coverage: 80
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ReadinessSnapshot | null>(null);

  function setNumber(field: keyof ReadinessCommand, value: string): void {
    setValues((current) => ({ ...current, [field]: Number(value) }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!releaseId.trim()) {
      setError("A release ID is required.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      setSnapshot(await onSubmit(releaseId.trim(), values));
    } catch (submitError) {
      setError(
        submitError instanceof Error ? submitError.message : "Readiness could not be calculated."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="form-card" aria-labelledby="readiness-title">
      <p className="section-label">RELEASE CERTIFICATION</p>
      <h2 id="readiness-title">Release readiness</h2>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="release-id">Release ID</label>
        <input
          id="release-id"
          value={releaseId}
          onChange={(event) => setReleaseId(event.target.value)}
          aria-required="true"
        />
        <label htmlFor="release-version">Expected version</label>
        <input
          id="release-version"
          type="number"
          min="0"
          value={values.expected_version}
          onChange={(event) => setNumber("expected_version", event.target.value)}
        />
        <label htmlFor="applicable-gates">Applicable gates</label>
        <input
          id="applicable-gates"
          type="number"
          min="0"
          value={values.applicable_gate_count}
          onChange={(event) => setNumber("applicable_gate_count", event.target.value)}
        />
        <label htmlFor="passed-gates">Passed gates</label>
        <input
          id="passed-gates"
          type="number"
          min="0"
          value={values.passed_gate_count}
          onChange={(event) => setNumber("passed_gate_count", event.target.value)}
        />
        <label htmlFor="gate-failures">Unwaived gate failures</label>
        <input
          id="gate-failures"
          type="number"
          min="0"
          value={values.unwaived_gate_failures}
          onChange={(event) => setNumber("unwaived_gate_failures", event.target.value)}
        />
        <label htmlFor="test-pass-rate">Test pass rate (%)</label>
        <input
          id="test-pass-rate"
          type="number"
          min="0"
          max="100"
          value={values.test_pass_rate}
          onChange={(event) => setNumber("test_pass_rate", event.target.value)}
        />
        <label htmlFor="open-defects">Open defects</label>
        <input
          id="open-defects"
          type="number"
          min="0"
          value={values.open_defect_count}
          onChange={(event) => setNumber("open_defect_count", event.target.value)}
        />
        <label htmlFor="critical-defects">Critical defects</label>
        <input
          id="critical-defects"
          type="number"
          min="0"
          value={values.critical_defect_count}
          onChange={(event) => setNumber("critical_defect_count", event.target.value)}
        />
        <label htmlFor="automation-coverage">Automation coverage (%)</label>
        <input
          id="automation-coverage"
          type="number"
          min="0"
          max="100"
          value={values.automation_coverage}
          onChange={(event) => setNumber("automation_coverage", event.target.value)}
        />
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={loading}>
          {loading ? "Calculating…" : "Calculate readiness"}
        </button>
      </form>
      {snapshot ? (
        <div className="readiness-result" aria-live="polite">
          <p>
            <strong>{snapshot.recommendation}</strong> — weighted score {snapshot.score.toFixed(2)}%
          </p>
          <p>
            Gates {(snapshot.weights.gates * 100).toFixed(0)}% · Tests{" "}
            {(snapshot.weights.tests * 100).toFixed(0)}% · Defects{" "}
            {(snapshot.weights.defects * 100).toFixed(0)}% · Automation{" "}
            {(snapshot.weights.automation * 100).toFixed(0)}%
          </p>
          <p>
            Persisted release {snapshot.release_id}, version {snapshot.version}.
          </p>
        </div>
      ) : null}
    </section>
  );
}