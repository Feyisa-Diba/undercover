# Status

The claims pilot in `docs/PLAN.md` is built: all six phases are done.

The agent's harness in `docs/PLAN_HARNESS.md` is in progress: phases 1 to 5 of 6 are done, apart from the live checks of phases 3 and 4, which wait for a backend on port 8000 running the new code.

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

On September 27, 2026, `uv run -m agent` with `openai/gpt-6-luna` worked all 25 claims in 2 minutes 47 seconds: 17 approve, 5 decline and 3 refer. Three approvals were over $1,000 and waited for sign-off (CLM-1003, CLM-1008 and CLM-1011), and every other approval was paid its payout. These decisions have not yet been scored against the handlers' decisions in `data/evals/`.
