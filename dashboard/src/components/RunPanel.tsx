import { api, type Run } from "../api";
import { time } from "../format";
import { REFRESH_MS, useLoad } from "../useLoad";
import { TodoChip } from "./Chips";
import { Message } from "./Message";

export function RunPanel() {
  const { data: runs, error } = useLoad(api.listRuns, REFRESH_MS);

  return (
    <section className="panel" aria-labelledby="run-title">
      <h2 id="run-title">The agent's to-do list</h2>
      {!runs && <Message error={error} />}
      {runs?.length === 0 && (
        <p className="muted">
          No runs yet. The agent's to-do list appears here when a run starts.
        </p>
      )}
      {runs?.[0] && <RunDetails run={runs[0]} />}
    </section>
  );
}

function RunDetails({ run }: Readonly<{ run: Run }>) {
  const done = run.todos.filter((todo) => todo.status === "done").length;

  return (
    <>
      <p className="small muted">
        Run {run.run_id}, started at {time(run.started_at)}, for up to {run.cap}{" "}
        claims.{" "}
        {run.finished_at
          ? `Finished at ${time(run.finished_at)}.`
          : "The agent is working."}
      </p>
      {run.todos.length === 0 ? (
        <p className="muted">The agent hasn't written its to-do list yet.</p>
      ) : (
        <>
          <p className="todo-progress">
            {done} of {run.todos.length} done
          </p>
          <ol className="todos">
            {run.todos.map((todo) => (
              <li className="todo" key={todo.content}>
                <TodoChip status={todo.status} />
                <span>{todo.content}</span>
              </li>
            ))}
          </ol>
        </>
      )}
      {run.summary && (
        <>
          <h3>Summary</h3>
          <p className="run-summary">{run.summary}</p>
        </>
      )}
    </>
  );
}
