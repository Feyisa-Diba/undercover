# Status

The pilot is being built from `docs/PLAN.md`. Phase 1 of 6 is done.

- `backend/`: `GET /api/health`, and a SQLite database (`undercover.db`, or the path in `UNDERCOVER_DB`) seeded from `data/` with the 25 claims, all waiting. The backend seeds it on the first start.
- `agent/`: the skeleton's entry point `run(claim_id, thread_id)`, with one tool that calls the health route
- `dashboard/`: one page that shows whether the backend is up
- `e2e/`: one test of that page

## Commands

- `npm run dev`: the backend on port 8000 and the dashboard at http://localhost:5173
- `uv run -m backend.seed`: reset the queue, every claim back to waiting
- `npm run check`: every check
