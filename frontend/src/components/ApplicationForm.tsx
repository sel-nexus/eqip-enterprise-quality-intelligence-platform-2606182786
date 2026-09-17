import { useState } from "react";
import type { ApplicationCreateCommand, Criticality, Health, Tier } from "../types";

interface ApplicationFormProps {
  onSubmit: (command: ApplicationCreateCommand) => Promise<void>;
}

interface FormState {
  name: string;
  segment_id: string;
  product: string;
  criticality: Criticality;
  tier: Tier;
  owners: string;
  technology: string;
  health: Health;
}

const initialState: FormState = {
  name: "",
  segment_id: "SEG-HEALTH",
  product: "",
  criticality: "high",
  tier: "tier-1",
  owners: "",
  technology: "React, FastAPI",
  health: "amber"
};

/** Render the controlled create-application form. */
export function ApplicationForm({ onSubmit }: ApplicationFormProps): React.JSX.Element {
  const [form, setForm] = useState<FormState>(initialState);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Update one controlled form field. */
  function updateField(event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>): void {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  }

  /** Submit validated values to the parent API state manager. */
  async function handleSubmit(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    const owners = form.owners.split(",").map((owner) => owner.trim()).filter(Boolean);
    const technology = form.technology.split(",").map((item) => item.trim()).filter(Boolean);
    if (!form.name.trim() || !form.product.trim() || owners.length === 0 || technology.length === 0) {
      setError("Name, product, at least one owner, and technology are required.");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({
        name: form.name.trim(),
        segment_id: form.segment_id.trim(),
        product: form.product.trim(),
        criticality: form.criticality,
        tier: form.tier,
        owners,
        technology,
        health: form.health,
        expected_version: 0
      });
      setForm(initialState);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "The application could not be created.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel form-panel" aria-labelledby="create-application-heading">
      <div className="section-heading">
        <p className="section-label">GOVERNED INVENTORY</p>
        <h2 id="create-application-heading">Register application</h2>
        <p>Record ownership, operating tier, and current health for the governed portfolio.</p>
      </div>
      <form onSubmit={handleSubmit} noValidate>
        <div className="form-grid">
          <label htmlFor="application-name">Application name<span aria-hidden="true"> *</span>
            <input id="application-name" name="name" value={form.name} onChange={updateField} required aria-required="true" />
          </label>
          <label htmlFor="segment-id">Segment ID<span aria-hidden="true"> *</span>
            <input id="segment-id" name="segment_id" value={form.segment_id} onChange={updateField} required aria-required="true" />
          </label>
          <label htmlFor="product">Product<span aria-hidden="true"> *</span>
            <input id="product" name="product" value={form.product} onChange={updateField} required aria-required="true" />
          </label>
          <label htmlFor="owners">Owners<span aria-hidden="true"> *</span>
            <input id="owners" name="owners" value={form.owners} onChange={updateField} placeholder="u-42, u-64" required aria-required="true" />
          </label>
          <label htmlFor="criticality">Criticality
            <select id="criticality" name="criticality" value={form.criticality} onChange={updateField}>
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
            </select>
          </label>
          <label htmlFor="tier">Tier
            <select id="tier" name="tier" value={form.tier} onChange={updateField}>
              <option value="tier-1">Tier 1</option><option value="tier-2">Tier 2</option><option value="tier-3">Tier 3</option>
            </select>
          </label>
          <label htmlFor="technology">Technology<span aria-hidden="true"> *</span>
            <input id="technology" name="technology" value={form.technology} onChange={updateField} required aria-required="true" />
          </label>
          <label htmlFor="health">Health
            <select id="health" name="health" value={form.health} onChange={updateField}>
              <option value="green">Green</option><option value="amber">Amber</option><option value="red">Red</option>
            </select>
          </label>
        </div>
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        <button className="primary-button" type="submit" disabled={submitting}>
          {submitting ? "Registering…" : "Register application"}
        </button>
      </form>
    </section>
  );
}
