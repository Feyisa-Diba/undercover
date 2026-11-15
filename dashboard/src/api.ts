export type Status =
  "waiting" | "in_progress" | "waiting_for_sign_off" | "decided";
export type DecisionKind = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  submitted_on: string;
  amount_claimed: number;
  status: Status;
  decision: DecisionKind | null;
  payout: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: DecisionKind;
  payout: number;
  explanation: string;
  policy_section: string;
  decided_at: string;
  signed_off_by: string | null;
  signed_off_at: string | null;
}

export interface Payment {
  amount: number;
  paid_at: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: Status;
  thread_id: string | null;
  decision: Decision | null;
  payment: Payment | null;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface ClaimHistory {
  customer_id: string;
  name: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface PolicyWording {
  version: string;
  text: string;
}

export interface Instructions {
  text: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

export interface Step {
  step_id: number;
  thread_id: string;
  kind: "call" | "result" | "message";
  title: string;
  detail: string;
  created_at: string;
}

export const paths = {
  claims: "/api/claims",
  claim: (claimId: string) => `/api/claims/${claimId}`,
  steps: (claimId: string) => `/api/claims/${claimId}/steps`,
  signOff: (claimId: string) => `/api/claims/${claimId}/sign-off`,
  policy: (policyId: string) => `/api/policies/${policyId}`,
  history: (customerId: string) => `/api/customers/${customerId}/history`,
  wording: "/api/policy-wording",
  instructions: "/api/instructions",
  handlers: "/api/handlers",
};

async function read<T>(response: Response): Promise<T> {
  if (response.ok) return (await response.json()) as T;
  const body = (await response.json()) as { detail?: unknown };
  throw new Error(
    typeof body.detail === "string"
      ? body.detail
      : `The request failed with status ${String(response.status)}.`,
  );
}

export async function getJson<T>(path: string): Promise<T> {
  return read<T>(await fetch(path));
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  return read<T>(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  );
}
