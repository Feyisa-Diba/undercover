import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { parseRoute } from "./route";
import {
  claimRoutes,
  instructions,
  queue,
  stubApi,
  waitingClaim,
  wording,
} from "./testing";

beforeEach(() => {
  stubApi({
    "/api/claims": queue,
    ...claimRoutes(waitingClaim),
    "/api/instructions": instructions,
    "/api/policy-wording": wording,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

async function go(hash: string) {
  await act(async () => {
    window.location.hash = hash;
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

it("opens on the queue", async () => {
  render(<App />);
  expect(
    await screen.findByRole("heading", { name: "Claims queue" }),
  ).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBe("page");
});

it("follows the address to a claim and to the instructions", async () => {
  render(<App />);
  await go("#/claims/CLM-1001");
  expect(
    await screen.findByText(
      "My flight home from Rome on June 18 was canceled.",
    ),
  ).toBeDefined();
  await go("#/instructions");
  expect(
    await screen.findByRole("heading", { name: "Agent instructions" }),
  ).toBeDefined();
});

it("reads routes from the address", () => {
  expect(parseRoute("")).toEqual({ page: "queue" });
  expect(parseRoute("#/claims/CLM-1001")).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
  expect(parseRoute("#/nowhere")).toEqual({ page: "queue" });
});
