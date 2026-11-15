import { expect, test } from "@playwright/test";

test("the queue shows every claim waiting", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26);
  await expect(
    page.getByRole("group", { name: "Waiting", exact: true }),
  ).toHaveText("Waiting25");
  await expect(
    page.getByRole("group", { name: "Decided", exact: true }),
  ).toHaveText("Decided0");
});

test("a claim opens from the queue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(page).toHaveURL(/#\/claims\/CLM-1001$/);
  await expect(
    page.getByRole("heading", {
      name: "Flight home canceled by the airline, rebooked the next morning",
    }),
  ).toBeVisible();
  await expect(page.getByText(/^My flight home from Rome/)).toBeVisible();

  const claim = page.getByRole("region", { name: "The claim" });
  await expect(claim.locator("table.items tbody tr")).toHaveCount(3);
  await expect(claim.locator("table.items tfoot")).toContainText("$420.00");
  await expect(claim.locator("li.document")).toHaveCount(4);

  const policy = page.getByRole("region", { name: "Policy" });
  await expect(policy).toContainText("Premium");
  await expect(policy).toContainText("Jun 10, 2026 to Jun 18, 2026");
  await expect(page.getByRole("region", { name: "Customer" })).toContainText(
    "CLM-0412",
  );
  await expect(
    page.getByText("The agent hasn't decided this claim yet."),
  ).toBeVisible();
});

test("the instructions page shows the agent's prompt", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(
    page.getByRole("heading", { name: "Agent instructions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Instructions" }),
  ).toContainText("You are the UnderCover Agent.");
  await expect(
    page.getByRole("region", { name: /Policy wording/ }),
  ).toContainText("# UnderCover Travel Insurance: Policy Wording");
});
