# Status

The pilot is being built from `docs/PLAN.md`. Phases 1 to 3 of 6 are done.

- `backend/`: a SQLite database (`undercover.db`, or the path in `UNDERCOVER_DB`) seeded from `data/` with the 25 claims, all waiting. The backend seeds it on the first start. The read API serves the queue, each claim in full, policies, customers' claim history (without contact details), the policy wording and the handlers. The workflow API starts a claim, records the agent's steps and decision, pays approved claims and takes a handler's sign-off. A payout over $1,000 can't be paid until a handler signs off, and signing off releases the payment.
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Commands

- `npm run dev`: the backend on port 8000 and the dashboard at http://localhost:5173
- `uv run -m backend.seed`: reset the queue, every claim back to waiting
- `npm run check`: every check
