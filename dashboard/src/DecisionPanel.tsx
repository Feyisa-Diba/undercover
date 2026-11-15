import type { Claim, Decision } from "./api";
import { formatTime, money } from "./format";
import { SignOff, SignedOff } from "./SignOff";
import { DecisionChip } from "./ui";

function paymentText(claim: Claim, decision: Decision): string {
  if (claim.payment) {
    return `Paid ${money(claim.payment.amount)} on ${formatTime(claim.payment.paid_at)}`;
  }
  if (claim.status === "waiting_for_sign_off") {
    return "Waits for a handler's sign-off";
  }
  return decision.decision === "approve" ? "Not paid yet" : "Nothing to pay";
}

export function DecisionPanel({
  claim,
  onChange,
}: Readonly<{ claim: Claim; onChange: () => void }>) {
  const { decision } = claim;
  if (!decision) {
    return (
      <section className="panel decision" aria-labelledby="decision-heading">
        <h2 id="decision-heading">Decision</h2>
        <p className="muted">
          {claim.status === "in_progress"
            ? "The agent is working on this claim."
            : "The agent hasn't decided this claim yet."}
        </p>
      </section>
    );
  }

  return (
    <section className="panel decision" aria-labelledby="decision-heading">
      <div className="decision-head">
        <h2 id="decision-heading">Decision</h2>
        <DecisionChip decision={decision.decision} />
        <span className="decision-amount">{money(decision.payout)}</span>
      </div>
      <p className="explanation">{decision.explanation}</p>
      <dl className="facts">
        <dt>Policy section</dt>
        <dd>{decision.policy_section}</dd>
        <dt>Decided</dt>
        <dd>{formatTime(decision.decided_at)}</dd>
        <dt>Payment</dt>
        <dd>{paymentText(claim, decision)}</dd>
        {decision.signed_off_by && decision.signed_off_at && (
          <>
            <dt>Sign-off</dt>
            <dd>
              <SignedOff
                handlerId={decision.signed_off_by}
                at={decision.signed_off_at}
              />
            </dd>
          </>
        )}
      </dl>
      {claim.status === "waiting_for_sign_off" && (
        <SignOff
          claimId={claim.claim_id}
          payout={decision.payout}
          onSignedOff={onChange}
        />
      )}
    </section>
  );
}
