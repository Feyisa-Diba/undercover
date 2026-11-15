import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "./api";
import { ClaimPage } from "./ClaimPage";
import { claimRoutes, signOffClaim, stubApi, type Routes } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const signedOff: Claim = {
  ...signOffClaim,
  status: "decided",
  decision: {
    decision: "approve",
    payout: 1500,
    explanation: "Covered emergency treatment.",
    policy_section: "Section 7, Emergency Medical",
    decided_at: "2026-11-15T22:30:00+00:00",
    signed_off_by: "HND-02",
    signed_off_at: "2026-11-15T22:40:00+00:00",
  },
  payment: { amount: 1500, paid_at: "2026-11-15T22:40:00+00:00" },
};

async function signOffAs(name: string) {
  const decision = within(
    await screen.findByRole("region", { name: "Decision" }),
  );
  const picker = await decision.findByRole("combobox", { name: "Handler" });
  await within(picker).findByRole("option", { name: name });
  fireEvent.change(picker, {
    target: { value: name === "Marcus Oyelaran" ? "HND-02" : "HND-01" },
  });
  fireEvent.click(decision.getByRole("button", { name: "Sign off" }));
  return decision;
}

it("signs off the payout as the chosen handler and shows the payment", async () => {
  const routes: Routes = claimRoutes(signOffClaim);
  routes["POST /api/claims/CLM-1003/sign-off"] = signedOff;
  const requests = stubApi(routes);
  render(<ClaimPage claimId="CLM-1003" />);
  const decision = await signOffAs("Marcus Oyelaran");
  routes["/api/claims/CLM-1003"] = signedOff;

  expect(await decision.findByText(/^Paid \$1,500\.00 on /)).toBeDefined();
  expect(
    await decision.findByText(/^Signed off by Marcus Oyelaran on /),
  ).toBeDefined();
  expect(decision.queryByRole("button", { name: "Sign off" })).toBeNull();
  expect(requests).toContainEqual({
    key: "POST /api/claims/CLM-1003/sign-off",
    body: { handler_id: "HND-02" },
  });
});

it("shows why a sign-off was refused", async () => {
  const routes: Routes = claimRoutes(signOffClaim);
  routes["POST /api/claims/CLM-1003/sign-off"] = new Response(
    JSON.stringify({ detail: "Claim CLM-1003 isn't waiting for sign-off." }),
    { status: 409 },
  );
  stubApi(routes);
  render(<ClaimPage claimId="CLM-1003" />);
  const decision = await signOffAs("Dana Whitfield");
  expect((await decision.findByRole("alert")).textContent).toBe(
    "Claim CLM-1003 isn't waiting for sign-off.",
  );
});

it("names the handler who signed off", async () => {
  stubApi(claimRoutes(signedOff));
  render(<ClaimPage claimId="CLM-1003" />);
  expect(
    await screen.findByText(/^Signed off by Marcus Oyelaran on /),
  ).toBeDefined();
});
