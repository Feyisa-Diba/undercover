import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";
import { instructions, stubApi, wording } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions and the policy wording, read only", async () => {
  stubApi({
    "/api/instructions": instructions,
    "/api/policy-wording": wording,
  });
  render(<InstructionsPage />);
  expect(
    await screen.findByText(/# The UnderCover Agent\s+You decide claims\./),
  ).toBeDefined();
  expect(
    screen.getByText("# UnderCover Travel Insurance: Policy Wording"),
  ).toBeDefined();
  expect(screen.getByText("version 2026.1")).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("says when the instructions can't be loaded", async () => {
  stubApi({ "/api/policy-wording": wording });
  render(<InstructionsPage />);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "No route for /api/instructions",
  );
});
