# Code standards

1. Keep it simple, do not overcomplicate.
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.

## Structure

7. Every change must pass a pull request review, not just the checks. Tests, linters and type checkers can't see structure, so structure is your job.
8. One module per responsibility, with imports running one way. A module never reaches into another for a helper that happens to be there: move shared code to the module it belongs in.
9. Each outside service is called from one module, with its base URL in one place: the backend from `agent/api.py` and `dashboard/src/api.ts`, the model provider from `agent/harness.py`. No URL or API path appears anywhere else.
10. One way to do each thing. Before writing a helper, look for one that does the job; if you find two, merge them. The same check or message written twice is a missing helper.
11. When new work outgrows the code it extends, restructure the code first rather than bolting the new work on.

## Agents

12. Keep the harness, the tools and the business rules apart. `agent/harness.py` builds and runs the agents: the model, middleware and recovery. `agent/tools.py` holds every tool, each a thin wrapper over `agent/api.py`. The business rules live in the backend and in the agents' instructions.
13. Use LangChain's own mechanisms before writing your own: middleware for retries, limits and checks, `context_schema` with `ToolRuntime` to share a run's state with tools and middleware, not closures or classes that build tools.
14. Give an agent a goal, not a script. Its instructions say what a good result is, where to find what it needs, and the constraints it must respect. If the steps must happen in a fixed order, write them as code instead.
