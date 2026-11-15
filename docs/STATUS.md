# Status

The pilot from `docs/PLAN.md` is built: all six phases are done.

## What's built

- `backend/`: FastAPI and SQLite. The database (`undercover.db`, or the path in `UNDERCOVER_DB`) is seeded from `data/` with the 25 claims, all waiting, and the backend seeds it on the first start. Nothing reads `data/evals/`.
  - The read API serves the queue, each claim in full, policies, customers' claim history (without contact details), the policy wording, the handlers and the agent's instructions.
  - The workflow API (`backend/workflow.py`) starts a claim, records the agent's steps and its one decision, pays an approved claim its exact payout once, and takes a handler's sign-off. A payout over $1,000 (`payout_approval_limit` in `data/company.json`) can't be paid until a handler signs off, whatever the agent tries, and signing off releases the payment.
  - Every operation has an `operation_id`, a one-line docstring and no optional inputs; `backend/tests/test_openapi.py` checks this.
- `backend/instructions.md`: the agent's instructions, served read-only at `GET /api/instructions`.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on GPT-6 Luna at low effort, or the model in `MODEL_NAME`. `run(claim_id, thread_id)` starts the claim, uses the instructions and the policy wording as the system prompt, and posts every tool call, result and final message to the backend as a step. Its five tools (`get_claim`, `get_policy`, `get_claim_history`, `record_decision`, `pay_claim`) only work on the claim being decided, and it reads nothing but the API.
- `dashboard/`: the claims desk in the brand look, light and dark, refreshing every two seconds.
  - `#/`: the queue, with a count for each status.
  - `#/claims/CLM-1001`: a claim in full. The decision comes first, with a handler picker and Sign off button when a payout waits for sign-off. Then the agent's steps as they happen, the story, items, documents, the policy and the customer's history.
  - `#/instructions`: the agent's system prompt, read only.
- `e2e/`: Playwright tests of the queue, a claim, the instructions, live steps and sign-off. They start their own backend on port 8100 with a freshly seeded database in the temp folder, and Vite on port 5174, so `npm run check` never touches the queue that `npm run dev` serves. The tests that change claims (`actions.spec.ts`) run after the ones that read the fresh queue.

## Commands

- `npm run dev`: the backend on port 8000 and the dashboard at http://localhost:5173
- `uv run -m backend.seed`: reset the queue, every claim back to waiting
- `uv run -m agent`: work every waiting claim, one line per claim. `uv run -m agent CLM-1001` works one claim, or reruns a claim left in progress. The backend must be running
- `npm run check`: every check

## Known limits

- The agent works from the policy wording alone, as the spec asks for the pilot, so claims that need the claims manual are decided less well.
- If a run stops partway through, its claim stays in progress. `uv run -m agent <claim id>` runs it again.
- The agent hasn't been scored against the handlers' decisions in `data/evals/`.
- On a new OpenRouter account, GPT-6 Luna allows 20 requests a minute. The model client retries with backoff (`MAX_RETRIES` in `agent/main.py`), so a run over the whole queue waits rather than fails, and takes several minutes.
