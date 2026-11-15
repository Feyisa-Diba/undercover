# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 5 of 6 are done.

- `backend/`: a SQLite database (`undercover.db`, or the path in `UNDERCOVER_DB`) seeded from `data/` with the 25 claims, all waiting. The backend seeds it on the first start. The read API serves the queue, each claim in full, policies, customers' claim history (without contact details), the policy wording and the handlers. The workflow API starts a claim, records the agent's steps and decision, pays approved claims and takes a handler's sign-off. A payout over $1,000 can't be paid until a handler signs off, and signing off releases the payment.
- `backend/instructions.md`: the agent's instructions, served read-only at `GET /api/instructions`
- `agent/`: the UnderCover Agent. `run(claim_id, thread_id)` starts the claim, builds a `create_agent` agent on GPT-6 Luna (or `MODEL_NAME`) with the instructions and the policy wording as its system prompt, and posts every tool call, result and final message to the backend as a step. Its five tools (`get_claim`, `get_policy`, `get_claim_history`, `record_decision`, `pay_claim`) only work on the claim being decided, and it reads nothing but the API
- `dashboard/`: the claims desk in the brand look, light and dark. `#/` is the queue with a count for each status, `#/claims/CLM-1001` is a claim in full with its decision, policy and the customer's history, and `#/instructions` is the agent's system prompt, read only
- `e2e/`: Playwright tests of the queue, a claim and the instructions. They start their own backend on port 8100 with a freshly seeded database in the temp folder, and Vite on port 5174, so `npm run check` never touches the queue that `npm run dev` serves

## Commands

- `npm run dev`: the backend on port 8000 and the dashboard at http://localhost:5173
- `uv run -m backend.seed`: reset the queue, every claim back to waiting
- `uv run -m agent`: work every waiting claim, one line per claim. `uv run -m agent CLM-1001` works one claim, or reruns a claim left in progress. The backend must be running
- `npm run check`: every check
