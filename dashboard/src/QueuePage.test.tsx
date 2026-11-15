import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { QueuePage } from "./QueuePage";
import { queue, stubApi } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows every claim with where it stands", async () => {
  stubApi({ "/api/claims": queue });
  render(<QueuePage />);
  const rows = await screen.findAllByRole("row");
  expect(rows).toHaveLength(4);
  const first = within(rows[1]);
  expect(
    first.getByRole("link", { name: "CLM-1001" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1001");
  expect(first.getByText("Maya Patel")).toBeDefined();
  expect(first.getByText("Trip delay")).toBeDefined();
  expect(first.getByText("Jun 24, 2026")).toBeDefined();
  expect(first.getAllByText("$420.00")).toHaveLength(2);
  expect(first.getByText("Decided")).toBeDefined();
  expect(first.getByText("Approved")).toBeDefined();
  expect(within(rows[2]).getByText("$1,150.00")).toBeDefined();
});

it("counts the claims in each status", async () => {
  stubApi({ "/api/claims": queue });
  render(<QueuePage />);
  const waiting = await screen.findByRole("group", { name: "Waiting" });
  expect(waiting.textContent).toBe("Waiting2");
  expect(screen.getByRole("group", { name: "Decided" }).textContent).toBe(
    "Decided1",
  );
  expect(screen.getByRole("group", { name: "In progress" }).textContent).toBe(
    "In progress0",
  );
});

it("says when the queue can't be loaded", async () => {
  stubApi({});
  render(<QueuePage />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "No route for /api/claims",
  );
});
