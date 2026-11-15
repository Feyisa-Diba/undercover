import { vi } from "vitest";
import type {
  Claim,
  ClaimHistory,
  ClaimSummary,
  Handler,
  Instructions,
  Policy,
  PolicyWording,
  Step,
} from "./api";

export const waitingClaim: Claim = {
  claim_id: "CLM-1001",
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  claim_type: "trip_delay",
  submitted_on: "2026-06-24",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  summary: "Flight home canceled by the airline, rebooked the next morning",
  story: "My flight home from Rome on June 18 was canceled.",
  items: [
    {
      description: "Airport hotel, one night",
      category: "accommodation",
      amount: 245,
    },
    { description: "Dinner and breakfast", category: "meals", amount: 95 },
    { description: "Taxis", category: "transport", amount: 80 },
  ],
  amount_claimed: 420,
  documents: [
    {
      name: "Meridian Air cancellation notice",
      type: "carrier_report",
      content: "Flight MA 611 was canceled because of crew availability.",
    },
  ],
  status: "waiting",
  thread_id: null,
  decision: null,
  payment: null,
};

export const decidedClaim: Claim = {
  ...waitingClaim,
  status: "decided",
  thread_id: "thread-1",
  decision: {
    decision: "approve",
    payout: 420,
    explanation: "The delay was over six hours and the costs are covered.",
    policy_section: "Section 3, Trip Delay",
    decided_at: "2026-11-15T22:29:04+00:00",
    signed_off_by: null,
    signed_off_at: null,
  },
  payment: { amount: 420, paid_at: "2026-11-15T22:29:13+00:00" },
};

export const signOffClaim: Claim = {
  ...waitingClaim,
  claim_id: "CLM-1003",
  status: "waiting_for_sign_off",
  thread_id: "thread-3",
  decision: {
    decision: "approve",
    payout: 1500,
    explanation: "Covered emergency treatment.",
    policy_section: "Section 7, Emergency Medical",
    decided_at: "2026-11-15T22:30:00+00:00",
    signed_off_by: null,
    signed_off_at: null,
  },
};

export const policy: Policy = {
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  plan: "premium",
  add_ons: ["electronics_plus"],
  purchased_on: "2026-04-22",
  sold_through: "Meridian Air checkout",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  status: "active",
};

export const history: ClaimHistory = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      incident_date: "2024-08-09",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

export const queue: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    customer_name: "Maya Patel",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    amount_claimed: 420,
    status: "decided",
    decision: "approve",
    payout: 420,
  },
  {
    claim_id: "CLM-1002",
    customer_name: "Tomas Novak",
    claim_type: "baggage",
    submitted_on: "2026-07-20",
    amount_claimed: 1150,
    status: "waiting",
    decision: null,
    payout: null,
  },
  {
    claim_id: "CLM-1003",
    customer_name: "Ana Ruiz",
    claim_type: "emergency_medical",
    submitted_on: "2026-07-02",
    amount_claimed: 3800,
    status: "waiting",
    decision: null,
    payout: null,
  },
];

export const instructions: Instructions = {
  text: "# The UnderCover Agent\n\nYou decide claims.",
};

export const wording: PolicyWording = {
  version: "2026.1",
  text: "# UnderCover Travel Insurance: Policy Wording",
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-02",
    name: "Marcus Oyelaran",
    role: "Claims Handler",
    can_approve_over_limit: true,
  },
];

export const steps: Step[] = [
  {
    step_id: 1,
    thread_id: "thread-1",
    kind: "call",
    title: "get_claim",
    detail: "{}",
    created_at: "2026-11-15T22:28:44+00:00",
  },
  {
    step_id: 2,
    thread_id: "thread-1",
    kind: "result",
    title: "get_claim",
    detail: '{"claim_id": "CLM-1001"}',
    created_at: "2026-11-15T22:28:52+00:00",
  },
];

export type Routes = Record<string, unknown>;

/** Answer fetch from routes keyed by path, or "POST path" for a POST. */
export function stubApi(routes: Routes) {
  const requests: { key: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      const key = init?.method === "POST" ? `POST ${path}` : path;
      const body: unknown =
        typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
      requests.push({ key, body });
      const answer = routes[key];
      if (answer instanceof Response) return Promise.resolve(answer);
      if (answer === undefined) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: `No route for ${key}` }), {
            status: 404,
          }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(answer)));
    }),
  );
  return requests;
}

export function claimRoutes(claim: Claim): Routes {
  return {
    [`/api/claims/${claim.claim_id}`]: claim,
    [`/api/claims/${claim.claim_id}/steps`]: [],
    "/api/policies/POL-2001": policy,
    "/api/customers/CUS-3001/history": history,
    "/api/handlers": handlers,
  };
}
