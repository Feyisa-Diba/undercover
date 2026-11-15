import { expect, it } from "vitest";
import { addOnName, formatDate, formatTime, humanize, money } from "./format";

it("formats money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(money(1000.01)).toBe("$1,000.01");
});

it("formats calendar dates without shifting the day", () => {
  expect(formatDate("2026-06-24")).toBe("Jun 24, 2026");
  expect(formatDate("2026-01-01")).toBe("Jan 1, 2026");
});

it("formats a moment in local time", () => {
  expect(formatTime("2026-11-15T12:00:00+00:00")).toMatch(/^Nov 1[56], 2026, /);
});

it("turns codes into labels", () => {
  expect(humanize("emergency_medical")).toBe("Emergency medical");
  expect(addOnName("pre_existing_waiver")).toBe(
    "Pre-Existing Condition Waiver",
  );
  expect(addOnName("new_add_on")).toBe("New add on");
});
