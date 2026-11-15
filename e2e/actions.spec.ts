import { expect, test, type APIRequestContext } from "@playwright/test";

async function post(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(path, { data });
  expect(response.ok()).toBe(true);
}

function step(kind: string, title: string, detail: string) {
  return { thread_id: "e2e", kind, title, detail };
}

test("the agent's steps appear while it works", async ({ page, request }) => {
  await post(request, "/api/claims/CLM-1010/start", { thread_id: "e2e" });
  await page.goto("/#/claims/CLM-1010");
  await expect(page.locator(".page-head .chip")).toHaveText("In progress");
  await expect(
    page.getByText("The agent is working on this claim."),
  ).toBeVisible();

  const steps = page.getByRole("region", { name: "The agent's steps" });
  await post(
    request,
    "/api/claims/CLM-1010/steps",
    step("call", "get_policy", "{}"),
  );
  await expect(steps.getByRole("listitem")).toHaveCount(1);
  await expect(steps).toContainText("Called get_policy");

  await post(
    request,
    "/api/claims/CLM-1010/steps",
    step("message", "Agent", "Referred for a handler's judgment."),
  );
  await expect(steps.getByRole("listitem")).toHaveCount(2);
  await expect(steps).toContainText("Referred for a handler's judgment.");

  await post(request, "/api/claims/CLM-1010/decision", {
    explanation: "This needs a handler's judgment.",
    policy_section: "Section 7, Emergency Medical",
    decision: "refer",
    payout: 0,
  });
  await expect(page.locator(".page-head .chip")).toHaveText("Decided");
  await expect(page.getByRole("region", { name: "Decision" })).toContainText(
    "Referred",
  );
});

test("a handler signs off a payout over $1,000", async ({ page, request }) => {
  await post(request, "/api/claims/CLM-1003/start", { thread_id: "e2e" });
  await post(request, "/api/claims/CLM-1003/decision", {
    explanation: "Covered emergency treatment.",
    policy_section: "Section 7, Emergency Medical",
    decision: "approve",
    payout: 1500,
  });
  await page.goto("/#/claims/CLM-1003");
  await expect(page.locator(".page-head .chip")).toHaveText(
    "Waiting for sign-off",
  );
  const decision = page.getByRole("region", { name: "Decision" });
  await expect(decision).toContainText(
    "Payment of $1,500.00 waits for a handler's sign-off.",
  );

  await decision
    .getByRole("combobox", { name: "Handler" })
    .selectOption({ label: "Dana Whitfield" });
  await decision.getByRole("button", { name: "Sign off" }).click();

  await expect(page.locator(".page-head .chip")).toHaveText("Decided");
  await expect(decision).toContainText("Paid $1,500.00");
  await expect(decision).toContainText("Signed off by Dana Whitfield");
  await expect(decision.getByRole("button", { name: "Sign off" })).toHaveCount(
    0,
  );
});
