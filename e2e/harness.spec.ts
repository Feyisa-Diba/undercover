import { type APIRequestContext, expect, test } from "@playwright/test";

// These tests stand in for the agent by calling the API through the
// dashboard's proxy, and watch the pages update without a reload.

async function send(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(path, { data });
  expect(response.ok()).toBe(true);
  return (await response.json()) as Record<string, unknown>;
}

test("the queue page shows the agent's to-do list", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const panel = page.locator("section", {
    has: page.getByRole("heading", { name: "The agent's to-do list" }),
  });
  await expect(panel.getByText(/No runs yet/)).toBeVisible();

  const run = await send(request, "/api/runs", { cap: 2 });
  const todos = (first: string, second: string) => ({
    todos: [
      { content: "CLM-1001 Trip delay in Rome", status: first },
      { content: "CLM-1002 Lost suitcase", status: second },
    ],
  });
  const path = `/api/runs/${String(run.run_id)}`;
  const written = await request.put(`${path}/todos`, {
    data: todos("in_progress", "todo"),
  });
  expect(written.ok()).toBe(true);
  await expect(panel.getByText("0 of 2 done")).toBeVisible();
  await expect(panel.getByText("CLM-1001 Trip delay in Rome")).toBeVisible();
  await expect(panel.getByText("In progress", { exact: true })).toBeVisible();
  await expect(panel.getByText("To do", { exact: true })).toBeVisible();
  await expect(panel.getByText(/for up to 2 claims/)).toBeVisible();

  await request.put(`${path}/todos`, { data: todos("done", "done") });
  await send(request, `${path}/finish`, {
    summary: "Worked 2 claims: both approved.",
  });
  await expect(panel.getByText("2 of 2 done")).toBeVisible();
  await expect(panel.getByText("Done", { exact: true })).toHaveCount(2);
  await expect(
    panel.getByText("Worked 2 claims: both approved."),
  ).toBeVisible();
  await expect(panel.getByText(/Finished at/)).toBeVisible();
});

test("a claim that fails twice is left for a handler", async ({
  page,
  request,
}) => {
  await page.goto("/claims/CLM-1012");
  for (const [thread, reason] of [
    ["e2e-3", "RuntimeError: The model provider is down"],
    ["e2e-4", "The agent finished without recording a decision"],
  ]) {
    await send(request, "/api/claims/CLM-1012/start", { thread_id: thread });
    await send(request, "/api/claims/CLM-1012/release", { reason });
  }
  await expect(
    page.locator(".claim-heading").getByText("Left for a handler"),
  ).toBeVisible();
  await expect(
    page.getByText(
      "The agent couldn't finish this claim. It's left for a handler.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Failed")).toHaveCount(2);
  await expect(
    page.getByText("RuntimeError: The model provider is down"),
  ).toBeVisible();
  await expect(
    page.getByText("The agent finished without recording a decision"),
  ).toBeVisible();
});

test("the claim page lists the sections the agent read", async ({
  page,
  request,
}) => {
  await send(request, "/api/claims/CLM-1014/start", { thread_id: "e2e-5" });
  await page.goto("/claims/CLM-1014");
  const panel = page.locator("section", {
    has: page.getByRole("heading", { name: "Sections read" }),
  });
  await expect(panel.getByText(/appear here/)).toBeVisible();

  await send(request, "/api/claims/CLM-1014/reads", {
    document: "policy_wording",
    section: 5,
  });
  await send(request, "/api/claims/CLM-1014/reads", {
    document: "claims_manual",
    section: 7,
  });
  await expect(panel.getByRole("listitem")).toHaveText([
    "Policy wording 5. Baggage and Personal Effects",
    "Claims manual 7. Interpretation notes",
  ]);
});
