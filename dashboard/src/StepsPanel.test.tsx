import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Step } from "./api";
import { StepsPanel } from "./StepsPanel";
import { steps, stubApi, type Routes } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const message: Step = {
  step_id: 3,
  thread_id: "thread-1",
  kind: "message",
  title: "Agent",
  detail: "Approved and paid $420.00.",
  created_at: "2026-11-15T22:29:19+00:00",
};

it("shows the steps in order, with results folded away", async () => {
  const call: Step = { ...steps[0], step_id: 0, detail: '{"amount": 420}' };
  stubApi({ "/api/claims/CLM-1001/steps": [call, ...steps, message] });
  render(<StepsPanel claimId="CLM-1001" />);
  const items = await screen.findAllByRole("listitem");
  expect(items.map((item) => item.className)).toEqual([
    "step step-call",
    "step step-call",
    "step step-result",
    "step step-message",
  ]);
  expect(items[0]?.textContent).toMatch(/^Called get_claim\{"amount": 420\}/);
  expect(items[1]?.textContent).toMatch(/^Called get_claim\d/);
  const result = items[2]?.querySelector("details");
  expect(result?.open).toBe(false);
  expect(result?.textContent).toContain("Show the result of get_claim");
  expect(result?.querySelector("pre")?.textContent).toBe(
    '{\n  "claim_id": "CLM-1001"\n}',
  );
  expect(items[3]?.textContent).toContain("Approved and paid $420.00.");
});

it("shows a result that isn't JSON as it came", async () => {
  const result: Step = { ...steps[1], detail: "Internal Server Error" };
  stubApi({ "/api/claims/CLM-1001/steps": [result] });
  render(<StepsPanel claimId="CLM-1001" />);
  expect(await screen.findByText("Internal Server Error")).toBeDefined();
});

it("picks up new steps while the agent works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes: Routes = { "/api/claims/CLM-1001/steps": steps };
  stubApi(routes);
  render(<StepsPanel claimId="CLM-1001" />);
  expect(await screen.findAllByRole("listitem")).toHaveLength(2);
  routes["/api/claims/CLM-1001/steps"] = [...steps, message];
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
  expect(await screen.findByText("Approved and paid $420.00.")).toBeDefined();
});

it("says when the agent hasn't started", async () => {
  stubApi({ "/api/claims/CLM-1001/steps": [] });
  render(<StepsPanel claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent hasn't worked on this claim yet."),
  ).toBeDefined();
});
