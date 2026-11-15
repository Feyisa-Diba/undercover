import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "./api";
import { ClaimPage } from "./ClaimPage";
import {
  claimRoutes,
  decidedClaim,
  signOffClaim,
  stubApi,
  waitingClaim,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function section(name: string) {
  return within(screen.getByRole("region", { name }));
}

it("shows a decided claim with its decision and payment", async () => {
  stubApi(claimRoutes(decidedClaim));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", {
      name: "Flight home canceled by the airline, rebooked the next morning",
    }),
  ).toBeDefined();
  const decision = section("Decision");
  expect(decision.getByText("Approved")).toBeDefined();
  expect(decision.getByText("$420.00")).toBeDefined();
  expect(
    decision.getByText(
      "The delay was over six hours and the costs are covered.",
    ),
  ).toBeDefined();
  expect(decision.getByText("Section 3, Trip Delay")).toBeDefined();
  expect(
    decision.getByText(/^Paid \$420\.00 on Nov 1[56], 2026/),
  ).toBeDefined();
});

it("shows the claim's story, items, documents, policy and history", async () => {
  stubApi(claimRoutes(waitingClaim));
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByText("My flight home from Rome on June 18 was canceled.");
  const claim = section("The claim");
  expect(claim.getByText("Jun 18, 2026, Rome, Italy")).toBeDefined();
  expect(claim.getByText("Airport hotel, one night")).toBeDefined();
  expect(claim.getByText("Total claimed")).toBeDefined();
  expect(claim.getByText("$420.00")).toBeDefined();
  expect(claim.getByText("Carrier report")).toBeDefined();

  const policy = within(await screen.findByRole("region", { name: "Policy" }));
  expect(await policy.findByText("Premium")).toBeDefined();
  expect(policy.getByText("Electronics Plus")).toBeDefined();
  expect(policy.getByText("Jun 10, 2026 to Jun 18, 2026")).toBeDefined();
  expect(policy.getByText("$3,100.00")).toBeDefined();

  const customer = section("Customer");
  expect(await customer.findByText("Maya Patel")).toBeDefined();
  expect(customer.getByText("CLM-0412")).toBeDefined();
});

it("says when the agent hasn't decided a claim", async () => {
  stubApi(claimRoutes(waitingClaim));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent hasn't decided this claim yet."),
  ).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();
});

it("says when the agent is working on a claim", async () => {
  stubApi(claimRoutes({ ...waitingClaim, status: "in_progress" }));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent is working on this claim."),
  ).toBeDefined();
});

it("shows a payout that waits for sign-off", async () => {
  stubApi(claimRoutes(signOffClaim));
  render(<ClaimPage claimId="CLM-1003" />);
  expect(
    await screen.findByText(
      "Payment of $1,500.00 waits for a handler's sign-off.",
    ),
  ).toBeDefined();
  expect(screen.getByText("Waits for a handler's sign-off")).toBeDefined();
  expect(screen.getByText("Waiting for sign-off")).toBeDefined();
});

it("says when a declined claim has nothing to pay", async () => {
  const declined: Claim = {
    ...decidedClaim,
    payment: null,
    decision: {
      decision: "decline",
      payout: 0,
      explanation: "The wording doesn't cover it.",
      policy_section: "Section 9, General exclusions",
      decided_at: "2026-11-15T22:29:04+00:00",
      signed_off_by: null,
      signed_off_at: null,
    },
  };
  stubApi(claimRoutes(declined));
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Nothing to pay")).toBeDefined();
});

it("says when a claim can't be found", async () => {
  stubApi({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "No route for /api/claims/CLM-9999",
  );
});
