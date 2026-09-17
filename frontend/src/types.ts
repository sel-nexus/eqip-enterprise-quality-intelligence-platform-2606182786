/** Describe governed portfolio API contracts consumed by the dashboard. */

export type Criticality = "low" | "medium" | "high" | "critical";
export type Tier = "tier-1" | "tier-2" | "tier-3";
export type Health = "green" | "amber" | "red";

export interface ApplicationCreateCommand {
  name: string;
  segment_id: string;
  product: string;
  criticality: Criticality;
  tier: Tier;
  owners: string[];
  technology: string[];
  health: Health;
  expected_version: number;
}

export interface ApplicationRecord extends ApplicationCreateCommand {
  application_id: string;
  lifecycle: "active";
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ApiEnvelope<T> {
  data: T;
  correlation_id: string;
}

export interface ApplicationListData {
  items: ApplicationRecord[];
  total: number;
}

export interface ProblemDetails {
  title: string;
  status: number;
  detail: string;
  correlation_id?: string;
}
