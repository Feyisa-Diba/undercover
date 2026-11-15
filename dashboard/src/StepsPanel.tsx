import { paths, type Step } from "./api";
import { formatClock } from "./format";
import { Loading, Problem } from "./ui";
import { REFRESH_MS, useApi } from "./useApi";

/** Show JSON indented, and anything else as it came. */
function pretty(detail: string): string {
  try {
    return JSON.stringify(JSON.parse(detail), null, 2);
  } catch {
    return detail;
  }
}

function StepItem({ step }: Readonly<{ step: Step }>) {
  const time = (
    <time className="step-time" dateTime={step.created_at}>
      {formatClock(step.created_at)}
    </time>
  );
  switch (step.kind) {
    case "call":
      return (
        <li className="step step-call">
          <p>
            Called <code>{step.title}</code>
            {step.detail !== "{}" && (
              <code className="args">{step.detail}</code>
            )}
            {time}
          </p>
        </li>
      );
    case "result":
      return (
        <li className="step step-result">
          <details>
            <summary>
              Show the result of <code>{step.title}</code>
              {time}
            </summary>
            <pre>{pretty(step.detail)}</pre>
          </details>
        </li>
      );
    case "message":
      return (
        <li className="step step-message">
          <p>
            {step.detail}
            {time}
          </p>
        </li>
      );
  }
}

export function StepsPanel({ claimId }: Readonly<{ claimId: string }>) {
  const { data: steps, error } = useApi<Step[]>(
    paths.steps(claimId),
    REFRESH_MS,
  );
  return (
    <section className="panel" aria-labelledby="steps-heading">
      <h2 id="steps-heading">The agent&apos;s steps</h2>
      {error && <Problem message={error} />}
      {!error && !steps && <Loading />}
      {steps?.length === 0 && (
        <p className="muted">The agent hasn&apos;t worked on this claim yet.</p>
      )}
      {steps && steps.length > 0 && (
        <ol className="steps">
          {steps.map((step) => (
            <StepItem key={step.step_id} step={step} />
          ))}
        </ol>
      )}
    </section>
  );
}
