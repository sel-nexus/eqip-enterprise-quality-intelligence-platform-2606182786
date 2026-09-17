import type {
  ApiEnvelope,
  ApplicationCreateCommand,
  ApplicationListData,
  ApplicationRecord,
  ProblemDetails
} from "../types";

const apiBaseUrl = import.meta.env.VITE_API_URL ?? "";

/** Convert failed API responses into useful UI errors. */
async function readError(response: Response): Promise<never> {
  let problem: ProblemDetails | null = null;
  try {
    problem = (await response.json()) as ProblemDetails;
  } catch {
    // Non-JSON error responses still receive a useful generic message.
  }
  throw new Error(problem?.detail ?? `Request failed with status ${response.status}.`);
}

/** Create a governed application through the same-origin API. */
export async function createApplication(command: ApplicationCreateCommand): Promise<ApplicationRecord> {
  const response = await fetch(`${apiBaseUrl}/api/v1/applications`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(command)
  });
  if (!response.ok) {
    return readError(response);
  }
  const envelope = (await response.json()) as ApiEnvelope<ApplicationRecord>;
  return envelope.data;
}

/** Load the bounded governed application portfolio. */
export async function listApplications(): Promise<ApplicationListData> {
  const response = await fetch(`${apiBaseUrl}/api/v1/applications?limit=50&offset=0`);
  if (!response.ok) {
    return readError(response);
  }
  const envelope = (await response.json()) as ApiEnvelope<ApplicationListData>;
  return envelope.data;
}
