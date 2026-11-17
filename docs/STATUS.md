# Status

The claims pilot in `docs/PLAN.md` is built: all six phases are done.

The agent's harness in `docs/PLAN_HARNESS.md` is built: phases 1 to 5 are done, including their live checks, and so are phase 6's documents. Phase 6's live trial found two problems, now fixed and tested with stub models; the live retest of those fixes is still to do (see "Last live run" and "Known limitations").

The code review in `docs/HUMAN_REVIEW_HARNESS.md` is answered. The agent is restructured into `api.py`, `tools.py` and `harness.py`, both agents' instructions give a goal instead of a script, and the backend and the dashboard each keep their API prefix in one place. `docs/CODE_STANDARDS.md` (Structure and Agents) and `docs/PROCESS.md` (a design in every plan, and a review of every phase's diff before it's committed) now ask for what the review found missing.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173.
- `uv run -m backend.seed` rebuilds the database from `data/`, putting every claim back in the queue.
- `uv run -m agent --cap 5` starts a run of the queue agent that works at most five claims and leaves the rest waiting. It prints the model and the cap, a line for each claim as it comes back, then the summary for the handlers. `uv run -m agent` works every waiting claim the same way.
- `uv run -m agent CLM-1001` works one claim with the claim agent and prints one line, such as `CLM-1001  approve  $420.00  paid`. If the claim can't be started, it exits with the backend's reason, such as `Claim CLM-1001 is not waiting`.
- The agent uses the real model through OpenRouter: DeepSeek V4.1 Flash with low reasoning effort by default, or the model in `MODEL_NAME`.

## Built

- `backend/`: SQLite database seeded from `data/` (never `data/evals/`), at `undercover.db` or the path in `UNDERCOVER_DB`, created on startup when missing. The policy wording and the claims manual are stored in numbered sections, split on their `## N. Title` headings.
  - Every operation sits on one `APIRouter` with the `/api` prefix. `find_claim_in` makes every check that a claim has the status an operation needs.
  - Read operations: `health`, `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `list_handlers`, `list_steps`, `get_instructions`, `list_sections`, `search_sections`, `list_runs`.
  - Workflow operations: `start_claim`, `record_step`, `read_section`, `record_decision`, `pay_claim`, `sign_off_claim`, `release_claim`.
  - Run operations: `start_run`, `write_todos`, `finish_run`.
  - A claim moves from waiting to in progress to decided, or to waiting for sign-off when an approval pays over the limit in `company.json`. `pay_claim` refuses such a payout with a 403 until a handler signs off, and signing off pays it.
  - `start_claim` counts attempts. `release_claim` records the reason as an `error` step and puts a claim in progress back to waiting, or leaves it for a handler after its second attempt.
  - `read_section` returns a section in full and notes the read on a claim in progress, and `get_claim` lists the sections read. `search_sections` ranks sections by how many of the query's words they use.
  - `get_instructions` serves each agent's instructions, written from the wording and the manual: `/api/instructions/queue` from `backend/instructions/queue.md` and `/api/instructions/claim` from `backend/instructions/claim.md`. Each gives its agent a goal, what a good result is and the constraints, with no fixed order of steps. A test checks that every operation follows the API rules.
- `agent/`: two agents built with `create_agent`, in three modules that import one way, `harness.py` to `tools.py` to `api.py`.
  - `api.py`: every call to the backend, one function per operation, with the base URL in one place. A refusal raises `api.Refused` with the status and the reason.
  - `tools.py`: all eleven tools, each a thin wrapper over `api.py` that gives the model the backend's JSON or its refusal. The claim agent's eight are named after backend operations: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `search_sections`, `read_section`, `record_decision` and `pay_claim`. The queue agent's three are `list_claims`, `write_todos` (for its run's to-do list) and `work_claim`, which hands a claim to a claim agent, one at a time, and refuses a new claim once the cap is reached. `work_claim` also keeps the claim's item on the to-do list in step: in progress while it's worked, then done, to do again or left for a handler as the claim comes back, even when the model hands over several claims at once. The queue agent's tools reach their run through `RunContext`, passed with `context_schema` and `ToolRuntime`.
  - `harness.py`: the model, the middleware and running the agents. `work_claim(claim_id)` starts the claim, runs a fresh claim agent and reports back in one line built from the claim's record, recording every tool call, tool result and message as a step. A claim still in progress after a failure, or after finishing with no decision, is released with the reason. `work_queue(cap)` releases any claim left in progress by a run that stopped, starts a run and runs the queue agent, printing each claim's line as it comes back. Its final reply is recorded as the run's summary; if it fails, the run is finished with "The run stopped early". Middleware retries a failed model call 3 times with backoff, stops a claim agent after 30 model calls, and, in an `after_model` hook, sends the queue agent back to work when it tries to finish with claims it could still work, at most 3 times. The model has a 120 second timeout.
- `dashboard/`: the queue (`/`), with counts for the five states, the agent's to-do list for the newest run (each item To do, In progress, Done or Left for a handler, then the run's summary when it finishes), and a line per claim. A claim in full (`/claims/:claimId`), with its policy, earlier claims, the decision and payment, the sections of the wording and the manual the agent read, the agent's steps as it works (failures shown as Failed), and a sign-off form for a held payout. The agent's instructions (`/instructions`) for running the queue and for working a claim, read only. The queue and a claim page refresh every two seconds. Every call to the backend goes through `dashboard/src/api.ts`. Styled to `BRAND.md` in light and dark mode.
- `e2e/`: tests of the three pages, the agent's steps appearing on a claim page, a handler signing off a held payout, the to-do list filling in and being ticked off, a claim left for a handler, and the sections read. Playwright runs its own backend on port 8001 with `e2e/undercover.db`, and its own dashboard on port 5174, so it can run next to `npm run dev`.

## Last live run

On November 16, 2026, on a fresh database with the default model, `deepseek/deepseek-v4.1-flash`:

- `uv run -m agent CLM-1005` approved the claim and paid $243.00 in 2 minutes 16 seconds. The claim agent read 14 of the 26 sections, 8 of them in the claims manual.
- `uv run -m agent --cap 5`, watched on the queue page, worked the five longest-waiting claims in 13 minutes: CLM-1001, CLM-1008, CLM-1011, CLM-1018 and CLM-1010. The to-do list filled in and was ticked off, and the run finished with every item done and 20 claims still waiting.
- A second capped run, started while the first was finishing, worked CLM-1010 again (see "Known limitations"), then CLM-1015, CLM-1003, CLM-1012 and CLM-1004, in 11 minutes.

Nine claims were decided across the two runs, and 16 are still waiting:

| Claim | Decision | Payout | Outcome |
|---|---|---|---|
| CLM-1001 | approve | $800.00 | Not paid. The payout should be $420.00 (below) |
| CLM-1003 | approve | $3,750.00 | Waiting for sign-off |
| CLM-1004 | approve | $186.00 | Paid |
| CLM-1008 | approve | $2,240.00 | Waiting for sign-off |
| CLM-1010 | decline | $0.00 | Worked by both runs |
| CLM-1011 | approve | $1,150.00 | Waiting for sign-off |
| CLM-1012 | decline | $0.00 | |
| CLM-1015 | decline | $0.00 | |
| CLM-1018 | refer | $0.00 | A required document is missing |

Every decision names a section and gives a reason, though three of the reasons run to four sentences, one more than asked. Every approval over $1,000 waits for sign-off with no payment, and CLM-1004 was paid exactly its payout. Each claim agent read 8 to 14 sections, at least 4 of them in the claims manual. These decisions have not been scored against the handlers' decisions in `data/evals/`.

The trial found two problems. Both are fixed, with tests on a stub model, but neither fix has been seen in a live run yet:

- The to-do list lagged behind the claims. The queue agent handed over two claims at once, so it couldn't update the list until both came back, and for a few minutes the list showed a decided claim as In progress. `work_claim` now keeps each claim's item in step.
- A claim agent recorded CLM-1001's decision with the plan's $800 Trip Delay maximum as the payout, then worked out that it should be $420 and tried to record it again. The backend refused the second decision, and refused to pay $420 against an $800 payout, so the claim stands approved at $800 and unpaid. The claim instructions now say that a recorded decision is final, so the checks and the payout come first.

## Known limitations

- Run one queue run at a time. A run starts by releasing every claim in progress, on the assumption that a stopped run left it, so a second run releases a claim the first is still working. In the trial, the second run released CLM-1010 and started it again, so two claim agents worked it at once, both recording steps on it. One recorded the decline, the other's decision was refused, and the claim used up both its attempts.
- A run stopped with Ctrl+C, or whose process is killed, is never finished, and the queue page shows the agent still working until a newer run starts. Its claims in progress are released when the next run starts.
- A recorded decision can't be changed, by the agent or by a handler, and the dashboard has no way to correct or flag one. An approval within the limit that the agent didn't pay, like CLM-1001, stays unpaid with nothing to prompt a handler.
- A claim takes the default model about two minutes, mostly spent reading sections, so a run of five takes 11 to 13 minutes.
