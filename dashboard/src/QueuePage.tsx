import { paths, type ClaimSummary } from "./api";
import { STATUSES, STATUS_LABELS, formatDate, humanize, money } from "./format";
import { DecisionChip, Loading, Problem, StatusChip } from "./ui";
import { useApi } from "./useApi";

export function QueuePage() {
  const { data: claims, error } = useApi<ClaimSummary[]>(paths.claims);
  if (error) return <Problem message={error} />;
  if (!claims) return <Loading />;

  return (
    <>
      <div className="page-head">
        <h1>Claims queue</h1>
      </div>
      <section className="tiles" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <div
            key={status}
            className="tile panel"
            role="group"
            aria-label={STATUS_LABELS[status]}
          >
            <span className={`dot status-${status}`} />
            <span className="tile-label">{STATUS_LABELS[status]}</span>
            <span className="tile-count">
              {claims.filter((c) => c.status === status).length}
            </span>
          </div>
        ))}
      </section>
      <section className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Customer</th>
              <th scope="col">Type</th>
              <th scope="col">Submitted</th>
              <th scope="col" className="num">
                Claimed
              </th>
              <th scope="col">Status</th>
              <th scope="col">Decision</th>
              <th scope="col" className="num">
                Payout
              </th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td>
                  <a className="mono" href={`#/claims/${claim.claim_id}`}>
                    {claim.claim_id}
                  </a>
                </td>
                <td>{claim.customer_name}</td>
                <td>{humanize(claim.claim_type)}</td>
                <td>{formatDate(claim.submitted_on)}</td>
                <td className="num">{money(claim.amount_claimed)}</td>
                <td>
                  <StatusChip status={claim.status} />
                </td>
                <td>
                  {claim.decision && <DecisionChip decision={claim.decision} />}
                </td>
                <td className="num">
                  {claim.payout === null ? "" : money(claim.payout)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
