import type { DecisionKind, Status } from "./api";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const day = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});
const moment = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});
const clock = new Intl.DateTimeFormat("en-US", { timeStyle: "medium" });

export const STATUSES: Status[] = [
  "waiting",
  "in_progress",
  "waiting_for_sign_off",
  "decided",
];

export const STATUS_LABELS: Record<Status, string> = {
  waiting: "Waiting",
  in_progress: "In progress",
  waiting_for_sign_off: "Waiting for sign-off",
  decided: "Decided",
};

export const DECISION_LABELS: Record<DecisionKind, string> = {
  approve: "Approved",
  decline: "Declined",
  refer: "Referred",
};

const ADD_ONS: Record<string, string> = {
  adventure_sports: "Adventure Sports",
  pre_existing_waiver: "Pre-Existing Condition Waiver",
  electronics_plus: "Electronics Plus",
};

export function money(amount: number): string {
  return dollars.format(amount);
}

/** A calendar date such as 2026-06-24, shown as Jun 24, 2026. */
export function formatDate(iso: string): string {
  return day.format(new Date(iso));
}

/** A moment such as 2026-11-15T22:29:04+00:00, shown in local time. */
export function formatTime(iso: string): string {
  return moment.format(new Date(iso));
}

/** The time of day of a moment, such as 5:28:44 PM. */
export function formatClock(iso: string): string {
  return clock.format(new Date(iso));
}

/** A code such as trip_delay, shown as Trip delay. */
export function humanize(code: string): string {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function addOnName(code: string): string {
  return ADD_ONS[code] ?? humanize(code);
}
