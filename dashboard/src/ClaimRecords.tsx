import { paths, type ClaimHistory, type Policy } from "./api";
import { addOnName, formatDate, humanize, money } from "./format";
import { Loading, Problem } from "./ui";
import { useApi } from "./useApi";

export function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const { data: policy, error } = useApi<Policy>(paths.policy(policyId));
  return (
    <section className="panel" aria-labelledby="policy-heading">
      <h2 id="policy-heading">Policy</h2>
      {error && <Problem message={error} />}
      {!error && !policy && <Loading />}
      {policy && (
        <dl className="facts">
          <dt>Policy</dt>
          <dd className="mono">{policy.policy_id}</dd>
          <dt>Plan</dt>
          <dd>{humanize(policy.plan)}</dd>
          <dt>Add-ons</dt>
          <dd>
            {policy.add_ons.length
              ? policy.add_ons.map(addOnName).join(", ")
              : "None"}
          </dd>
          <dt>Bought</dt>
          <dd>
            {formatDate(policy.purchased_on)}, {policy.sold_through}
          </dd>
          <dt>Trip</dt>
          <dd>{policy.trip.destination}</dd>
          <dt>Dates</dt>
          <dd>
            {formatDate(policy.trip.departs_on)} to{" "}
            {formatDate(policy.trip.returns_on)}
          </dd>
          <dt>Trip cost</dt>
          <dd className="mono">{money(policy.trip.trip_cost)}</dd>
          <dt>Travelers</dt>
          <dd>{policy.travelers.join(", ")}</dd>
        </dl>
      )}
    </section>
  );
}

export function HistoryPanel({ customerId }: Readonly<{ customerId: string }>) {
  const { data: history, error } = useApi<ClaimHistory>(
    paths.history(customerId),
  );
  return (
    <section className="panel" aria-labelledby="history-heading">
      <h2 id="history-heading">Customer</h2>
      {error && <Problem message={error} />}
      {!error && !history && <Loading />}
      {history && (
        <>
          <p className="customer">
            <strong>{history.name}</strong>
            <span className="muted">
              {" "}
              Customer since {formatDate(history.customer_since)}
            </span>
          </p>
          <h3>Earlier claims</h3>
          {history.previous_claims.length === 0 && (
            <p className="muted">No earlier claims.</p>
          )}
          <ul className="history">
            {history.previous_claims.map((previous) => (
              <li key={previous.claim_id}>
                <span className="mono">{previous.claim_id}</span>{" "}
                <span className="muted">
                  {formatDate(previous.filed_on)},{" "}
                  {humanize(previous.claim_type)}
                </span>
                <br />
                {previous.summary}. {humanize(previous.outcome)},{" "}
                {money(previous.amount_paid)} paid.
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
