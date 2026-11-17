# Status

The claims pilot in `docs/PLAN.md` is built: all six phases are done.

The agent's harness in `docs/PLAN_HARNESS.md` is in progress: phases 1 to 4 of 6 are done, apart from the live checks of phases 3 and 4, which wait for a backend on port 8000 running the new code.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on http://localhost:5173.
- `uv run -m backend.seed` rebuilds the database from `data/`, putting every claim back in the queue.
- `uv run -m agent --cap 5` starts a run of the queue agent that works at most five claims and leaves the rest waiting. It prints the model and the cap, a line for each claim as it comes back, then the summary for the handlers. `uv run -m agent` works every waiting claim the same way.
- `uv run -m agent CLM-1001` works one claim with the claim agent and prints one line, such as `CLM-1001  approve  $420.00  paid`.
- The agent uses the real model through OpenRouter: DeepSeek V4.1 Flash with low reasoning effort by default, or the model in `MODEL_NAME`.

## Built

- `backend/`: SQLite database seeded from `data/` (never `data/evals/`), at `undercover.db` or the path in `UNDERCOVER_DB`, created on startup when missing. The policy wording and the claims manual are stored in numbered sections, split on their `## N. Title` headings.
  - Read operations: `health`, `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `list_handlers`, `list_steps`, `get_instructions`, `list_sections`, `search_sections`, `list_runs`.
  - Workflow operations: `start_claim`, `record_step`, `read_section`, `record_decision`, `pay_claim`, `sign_off_claim`, `release_claim`.
  - Run operations: `start_run`, `write_todos`, `finish_run`.
  - A claim moves from waiting to in progress to decided, or to waiting for sign-off when an approval pays over the limit in `company.json`. `pay_claim` refuses such a payout with a 403 until a handler signs off, and signing off pays it.
  - `start_claim` counts attempts. `release_claim` records the reason as an `error` step and puts a claim in progress back to waiting, or leaves it for a handler after its second attempt.
  - `read_section` returns a section in full and notes the read on a claim in progress, and `get_claim` lists the sections read. `search_sections` ranks sections by how many of the query's words they use.
  - `get_instructions` serves each agent's instructions, written from the wording and the manual: `/api/instructions/queue` from `backend/instructions/queue.md` and `/api/instructions/claim` from `backend/instructions/claim.md`. A test checks that every operation follows the API rules.
- `agent/`: two agents built with `create_agent`.
  - The queue agent (`agent/queue_agent.py`): `work_queue(cap)` releases any claim left in progress by a run that stopped, starts a run, and gives the queue agent three tools: `list_claims`, `write_todos` (for its run's to-do list) and `work_claim`, which hands a claim to a claim agent and refuses a new claim once the cap is reached. A completion check, an `after_model` hook, sends the agent back to work when it tries to finish with claims it could still work, at most 3 times. Its final reply is recorded as the run's summary. If it fails, the run is finished with "The run stopped early".
  - The claim agent (`agent/main.py`): `work_claim(claim_id)` starts the claim, runs a fresh claim agent with a new thread, and reports back in one line built from the claim's record. A claim still in progress after a failure, or after finishing with no decision, is released with the reason. The claim agent has eight tools named after backend operations: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `search_sections`, `read_section`, `record_decision` and `pay_claim`. It records every tool call, tool result and message as a step. Middleware retries a failed model call 3 times with backoff, and stops a claim agent after 30 model calls. The model has a 120 second timeout.
- `dashboard/`: the queue (`/`), with counts by state and a line per claim. A claim in full (`/claims/:claimId`), with its policy, earlier claims, the decision and payment, the agent's steps as it works, and a sign-off form for a held payout. The agent's instructions (`/instructions`) for running the queue and for working a claim, read only. The queue and a claim page refresh every two seconds. Styled to `BRAND.md` in light and dark mode.
- `e2e/`: tests of the three pages, the agent's steps appearing on a claim page, and a handler signing off a held payout. Playwright runs its own backend on port 8001 with `e2e/undercover.db`, and its own dashboard on port 5174, so it can run next to `npm run dev`.

## Last live run

On September 27, 2026, `uv run -m agent` with `openai/gpt-6-luna` worked all 25 claims in 2 minutes 47 seconds: 17 approve, 5 decline and 3 refer. Three approvals were over $1,000 and waited for sign-off (CLM-1003, CLM-1008 and CLM-1011), and every other approval was paid its payout. These decisions have not yet been scored against the handlers' decisions in `data/evals/`.
