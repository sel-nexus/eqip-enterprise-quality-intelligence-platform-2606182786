/** Describe governed portfolio API contracts consumed by the dashboard. */

declare global {
  const process: { env: Record<string, string | undefined> };
}

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

export type DemandState = "submitted" | "triaged" | "in_progress" | "completed" | "cancelled";
export type ReadinessRecommendation = "Ready" | "Conditional" | "Blocked";

export interface DemandTransitionCommand {
  destination: DemandState;
  expected_version: number;
  resolution_note?: string;
}

export interface DemandRecord {
  demand_id: string;
  state: DemandState;
  version: number;
  resolution_note: string | null;
  history: Array<Record<string, unknown>>;
  updated_at: string;
}

export interface ReadinessCommand {
  expected_version: number;
  applicable_gate_count: number;
  passed_gate_count: number;
  unwaived_gate_failures: number;
  test_pass_rate: number;
  open_defect_count: number;
  critical_defect_count: number;
  automation_coverage: number;
}

export interface ReadinessSnapshot {
  release_id: string;
  version: number;
  inputs: ReadinessCommand;
  weights: Record<"gates" | "tests" | "defects" | "automation", number>;
  score: number;
  recommendation: ReadinessRecommendation;
  timestamp: string;
}
