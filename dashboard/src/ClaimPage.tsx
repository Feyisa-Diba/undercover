import { paths, type Claim } from "./api";
import { HistoryPanel, PolicyPanel } from "./ClaimRecords";
import { DecisionPanel } from "./DecisionPanel";
import { formatDate, humanize, money } from "./format";
import { Loading, Problem, StatusChip } from "./ui";
import { useApi } from "./useApi";

function ClaimEvidence({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-labelledby="claim-heading">
      <h2 id="claim-heading">The claim</h2>
      <dl className="facts">
        <dt>Incident</dt>
        <dd>
          {formatDate(claim.incident_date)}, {claim.incident_location}
        </dd>
        <dt>Submitted</dt>
        <dd>{formatDate(claim.submitted_on)}</dd>
      </dl>
      <blockquote className="story">{claim.story}</blockquote>

      <h3>Items claimed</h3>
      <table className="items">
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col">Category</th>
            <th scope="col" className="num">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{humanize(item.category)}</td>
              <td className="num">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={2}>
              Total claimed
            </th>
            <td className="num">{money(claim.amount_claimed)}</td>
          </tr>
        </tfoot>
      </table>

      <h3>Documents</h3>
      <ul className="documents">
        {claim.documents.map((document) => (
          <li key={document.name} className="document">
            <p className="document-name">
              {document.name}{" "}
              <span className="muted">{humanize(document.type)}</span>
            </p>
            <p>{document.content}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const { data: claim, error } = useApi<Claim>(paths.claim(claimId));
  if (error) return <Problem message={error} />;
  if (!claim) return <Loading />;

  return (
    <>
      <a className="back" href="#/">
        Back to the queue
      </a>
      <div className="page-head">
        <div>
          <p className="eyebrow">
            <span className="mono">{claim.claim_id}</span>
            {" · "}
            {humanize(claim.claim_type)}
          </p>
          <h1>{claim.summary}</h1>
        </div>
        <StatusChip status={claim.status} />
      </div>
      <div className="claim-grid">
        <div className="stack">
          <DecisionPanel claim={claim} />
          <ClaimEvidence claim={claim} />
        </div>
        <aside className="stack">
          <PolicyPanel policyId={claim.policy_id} />
          <HistoryPanel customerId={claim.customer_id} />
        </aside>
      </div>
    </>
  );
}
