# Tech stack

- `backend/`: FastAPI and SQLite. Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount.
- `agent/`: two agents built with LangChain's `create_agent` on OpenRouter, and no other agent framework. The queue agent, entry point `work_queue(cap)`, plans a run as a to-do list and hands each claim to the claim agent, entry point `work_claim(claim_id)`, which works one claim from a clean start. Both reach claims, sections of the wording and the manual, runs and their instructions only through the backend's API. Their tools are named after the backend operations they call, apart from the queue agent's `work_claim`, which hands a claim to a claim agent. LangChain middleware retries failed model calls and limits a claim agent's model calls, and our own `after_model` hook checks for missed claims before a run finishes. They use `deepseek/deepseek-v4.1-flash` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React, Vite and TypeScript.
- `e2e/`: Playwright tests.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 26. The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
