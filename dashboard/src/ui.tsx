import type { DecisionKind, Status } from "./api";
import { DECISION_LABELS, STATUS_LABELS } from "./format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return (
    <span className={`chip status-${status}`}>{STATUS_LABELS[status]}</span>
  );
}

export function DecisionChip({
  decision,
}: Readonly<{ decision: DecisionKind }>) {
  return (
    <span className={`chip decision-${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}

export function Loading() {
  return <p className="notice">Loading…</p>;
}

export function Problem({ message }: Readonly<{ message: string }>) {
  return (
    <p className="notice problem" role="alert">
      {message}
    </p>
  );
}
