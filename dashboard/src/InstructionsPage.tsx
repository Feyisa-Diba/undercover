import { paths, type Instructions, type PolicyWording } from "./api";
import { Loading, Problem } from "./ui";
import { useApi } from "./useApi";

export function InstructionsPage() {
  const instructions = useApi<Instructions>(paths.instructions);
  const wording = useApi<PolicyWording>(paths.wording);
  const error = instructions.error ?? wording.error;
  if (error) return <Problem message={error} />;
  if (!instructions.data || !wording.data) return <Loading />;

  return (
    <>
      <div className="page-head">
        <h1>Agent instructions</h1>
      </div>
      <p className="lede">
        The UnderCover Agent&apos;s system prompt: its instructions, then the
        policy wording. Read only.
      </p>
      <div className="stack">
        <section className="panel" aria-labelledby="instructions-heading">
          <h2 id="instructions-heading">Instructions</h2>
          <pre className="prompt">{instructions.data.text}</pre>
        </section>
        <section className="panel" aria-labelledby="wording-heading">
          <h2 id="wording-heading">
            Policy wording{" "}
            <span className="muted mono">version {wording.data.version}</span>
          </h2>
          <pre className="prompt">{wording.data.text}</pre>
        </section>
      </div>
    </>
  );
}
