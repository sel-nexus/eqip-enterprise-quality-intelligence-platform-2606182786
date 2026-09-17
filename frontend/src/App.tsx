import { useCallback, useEffect, useState } from "react";
import { calculateReadiness, createApplication, listApplications, transitionDemand } from "./api/client";
import { ApplicationForm } from "./components/ApplicationForm";
import { ApplicationTable } from "./components/ApplicationTable";
import { DemandTransitionForm } from "./components/DemandTransitionForm";
import { ReadinessPanel } from "./components/ReadinessPanel";
import type { ApplicationCreateCommand, ApplicationRecord } from "./types";

/** Compose the governed portfolio dashboard and API state. */
export default function App(): React.JSX.Element {
  const [applications, setApplications] = useState<ApplicationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadPortfolio = useCallback(async (): Promise<void> => {
    setLoading(true);
    setLoadError(null);
    try {
      const result = await listApplications();
      setApplications(result.items ?? []);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "The portfolio could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, [loadPortfolio]);

  /** Create a record and update the visible persisted data set. */
  async function handleCreate(command: ApplicationCreateCommand): Promise<void> {
    const created = await createApplication(command);
    setApplications((current) => [created, ...current]);
    setNotice(`${created.application_id} is active in the governed portfolio.`);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div><p className="wordmark">EQIP</p><p className="workspace-name">Quality intelligence platform</p></div>
        <p className="environment">DEVELOPMENT CONTEXT</p>
      </header>
      <div className="content-grid">
        <section className="intro" aria-labelledby="page-title">
          <p className="section-label">PORTFOLIO GOVERNANCE</p>
          <h1 id="page-title">Application register</h1>
          <p>Establish the active inventory used by quality and release governance workflows.</p>
          {notice ? <p className="success-notice" aria-live="polite">{notice}</p> : null}
        </section>
        <ApplicationForm onSubmit={handleCreate} />
        <DemandTransitionForm onSubmit={transitionDemand} />
        <ReadinessPanel onSubmit={calculateReadiness} />
        <ApplicationTable applications={applications} loading={loading} error={loadError} onRetry={() => void loadPortfolio()} />
      </div>
    </main>
  );
}
