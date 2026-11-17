import { useCallback } from "react";
import { type AgentName, api } from "../api";
import { Message } from "../components/Message";
import { useLoad } from "../useLoad";

export function InstructionsPage() {
  return (
    <>
      <h1>Agent instructions</h1>
      <p className="lead">
        What the agent reads before it starts. It looks up the policy wording
        and the claims manual as it needs them. This page is read only.
      </p>
      <InstructionsPanel agent="claim" title="Working a claim" />
    </>
  );
}

function InstructionsPanel({
  agent,
  title,
}: Readonly<{ agent: AgentName; title: string }>) {
  const load = useCallback(() => api.getInstructions(agent), [agent]);
  const { data, error } = useLoad(load);
  const titleId = `${agent}-instructions`;

  return (
    <section className="panel" aria-labelledby={titleId}>
      <h2 id={titleId}>{title}</h2>
      {data ? (
        <pre className="instructions">{data.text}</pre>
      ) : (
        <Message error={error} />
      )}
    </section>
  );
}
