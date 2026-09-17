import type { ApplicationRecord } from "../types";

interface ApplicationTableProps {
  applications: ApplicationRecord[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

/** Render persisted applications and their collection states. */
export function ApplicationTable({
  applications,
  loading,
  error,
  onRetry
}: ApplicationTableProps): React.JSX.Element {
  if (loading) {
    return (
      <section className="panel table-panel" aria-live="polite">
        <p className="state-message">Loading governed applications…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel table-panel" role="alert">
        <p className="state-message">{error}</p>
        <button className="ghost-button" onClick={onRetry}>
          Retry
        </button>
      </section>
    );
  }

  if (applications.length === 0) {
    return (
      <section className="panel table-panel" aria-live="polite">
        <p className="state-message">No governed applications are recorded yet.</p>
      </section>
    );
  }

  return (
    <section className="panel table-panel" aria-labelledby="portfolio-heading">
      <div className="section-heading compact-heading">
        <p className="section-label">PERSISTED PORTFOLIO</p>
        <h2 id="portfolio-heading">Governed applications</h2>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Application</th>
              <th scope="col">Business ID</th>
              <th scope="col">Tier</th>
              <th scope="col">Health</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {applications.map((application) => (
              <tr key={application.application_id}>
                <td>
                  <strong>{application.name}</strong>
                  <span>{application.product}</span>
                </td>
                <td className="mono">{application.application_id}</td>
                <td>{application.tier}</td>
                <td>
                  <span className={`health health-${application.health}`} role="status">
                    {application.health}
                  </span>
                </td>
                <td>
                  <span className="status">{application.lifecycle}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}