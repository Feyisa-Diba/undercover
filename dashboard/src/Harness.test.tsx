import { act, cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import type { Claim, Run, Step, Todo } from "./api";
import { Refusal, claim, history, policy, stubApi, summary } from "./testing";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const startedAt = "2026-11-16T17:00:00+00:00";

const todos: Todo[] = [
  { content: "CLM-1001 Trip delay in Rome", status: "done" },
  { content: "CLM-1002 Lost suitcase", status: "in_progress" },
  { content: "CLM-1003 Medical bill in Lisbon", status: "todo" },
  { content: "CLM-1004 Stolen camera", status: "left_for_handler" },
];

const running: Run = {
  run_id: 2,
  cap: 5,
  started_at: startedAt,
  finished_at: null,
  summary: null,
  todos,
};

function showQueue(runs: Run[] | Refusal) {
  const routes: Record<string, unknown> = {
    "GET /api/claims": [
      summary,
      { ...summary, claim_id: "CLM-1004", status: "left_for_handler" },
    ],
    "GET /api/runs": runs,
  };
  stubApi(routes);
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  return routes;
}

async function todoPanel() {
  const heading = await screen.findByRole("heading", {
    name: "The agent's to-do list",
  });
  const panel = heading.closest("section");
  if (!panel) throw new Error("The to-do list isn't in a section");
  return within(panel);
}

function showClaim(shown: Claim, steps: Step[] = []) {
  stubApi({
    "GET /api/claims/CLM-1002": shown,
    "GET /api/claims/CLM-1002/steps": steps,
    "GET /api/policies/POL-2002": policy,
    "GET /api/customers/CUS-3002/claims": history,
    "GET /api/handlers": [],
  });
  render(
    <MemoryRouter initialEntries={["/claims/CLM-1002"]}>
      <App />
    </MemoryRouter>,
  );
}

it("shows the newest run's to-do list with each status", async () => {
  showQueue([running, { ...running, run_id: 1, todos: [] }]);
  const panel = await todoPanel();
  expect(await panel.findByText("1 of 4 done")).toBeDefined();
  expect(panel.getByText(/Run 2, started at/)).toBeDefined();
  expect(panel.getByText(/for up to 5\s+claims/)).toBeDefined();
  expect(panel.getByText(/The agent is working/)).toBeDefined();

  const items = panel.getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "DoneCLM-1001 Trip delay in Rome",
    "In progressCLM-1002 Lost suitcase",
    "To doCLM-1003 Medical bill in Lisbon",
    "Left for a handlerCLM-1004 Stolen camera",
  ]);
  const chip = within(items[3]).getByText("Left for a handler");
  expect(chip.className).toBe("chip todo-left_for_handler");
  expect(panel.queryByRole("heading", { name: "Summary" })).toBeNull();
});

it("shows a finished run with its summary", async () => {
  showQueue([
    {
      ...running,
      finished_at: "2026-11-16T17:04:00+00:00",
      summary: "Worked 4 claims.\nCLM-1004 needs a handler.",
      todos: todos.map((todo) => ({ ...todo, status: "done" })),
    },
  ]);
  const panel = await todoPanel();
  expect(await panel.findByText("4 of 4 done")).toBeDefined();
  expect(panel.getByText(/Finished at/)).toBeDefined();
  expect(panel.getByRole("heading", { name: "Summary" })).toBeDefined();
  expect(panel.getByText(/CLM-1004 needs a handler/)).toBeDefined();
});

it("says when there are no runs yet", async () => {
  showQueue([]);
  const panel = await todoPanel();
  expect(await panel.findByText(/No runs yet/)).toBeDefined();
});

it("says when the agent hasn't written its to-do list", async () => {
  showQueue([{ ...running, todos: [] }]);
  const panel = await todoPanel();
  expect(await panel.findByText(/hasn't written its to-do list/)).toBeDefined();
});

it("shows an error when the runs can't load", async () => {
  showQueue(new Refusal(500, "The backend is down"));
  const panel = await todoPanel();
  expect((await panel.findByRole("alert")).textContent).toBe(
    "The backend is down",
  );
});

it("ticks off the to-do list as the agent works", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const routes = showQueue([{ ...running, todos: todos.slice(1, 3) }]);
  const panel = await todoPanel();
  expect(await panel.findByText("0 of 2 done")).toBeDefined();

  routes["GET /api/runs"] = [
    {
      ...running,
      todos: todos
        .slice(1, 3)
        .map((todo) => ({ ...todo, status: "done" as const })),
    },
  ];
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(panel.getByText("2 of 2 done")).toBeDefined();
});

it("counts the claims left for a handler", async () => {
  showQueue([]);
  expect(await screen.findByLabelText("Left for a handler: 1")).toBeDefined();
  expect(screen.getByLabelText("Waiting: 1")).toBeDefined();
  const row = screen.getByRole("row", { name: /CLM-1004/ });
  expect(within(row).getByText("Left for a handler").className).toBe(
    "chip status-left_for_handler",
  );
});

it("lists the sections the agent read", async () => {
  showClaim({
    ...claim,
    status: "in_progress",
    sections_read: [
      { document: "policy_wording", section: 5, title: "Baggage" },
      { document: "claims_manual", section: 7, title: "Interpretation notes" },
    ],
  });
  const heading = await screen.findByRole("heading", { name: "Sections read" });
  const panel = within(heading.closest("section") ?? document.body);
  expect(
    panel.getAllByRole("listitem").map((item) => item.textContent),
  ).toEqual([
    "Policy wording 5. Baggage",
    "Claims manual 7. Interpretation notes",
  ]);
});

it("says when the agent hasn't read any sections", async () => {
  showClaim(claim);
  const heading = await screen.findByRole("heading", { name: "Sections read" });
  const panel = within(heading.closest("section") ?? document.body);
  expect(panel.getByText(/appear here/)).toBeDefined();
  expect(panel.queryByRole("listitem")).toBeNull();
});

it("shows a claim left for a handler and why", async () => {
  const failed = (step_id: number, content: string): Step => ({
    step_id,
    thread_id: `t-${String(step_id)}`,
    kind: "error",
    content,
    created_at: startedAt,
  });
  showClaim({ ...claim, status: "left_for_handler", attempts: 2 }, [
    failed(1, "RuntimeError: The model provider is down"),
    failed(2, "The agent finished without recording a decision"),
  ]);
  expect(
    await screen.findByText(
      "The agent couldn't finish this claim. It's left for a handler.",
    ),
  ).toBeDefined();
  expect(
    await screen.findByText("RuntimeError: The model provider is down", {
      exact: false,
    }),
  ).toBeDefined();
  const labels = screen.getAllByText("Failed");
  expect(labels).toHaveLength(2);
  expect(labels[0].closest("li")?.className).toBe("step step-error");
});
