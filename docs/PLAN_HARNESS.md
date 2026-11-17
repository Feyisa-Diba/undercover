# Plan: the agent's harness

This plan builds the brief in `HARNESS.md` on top of the finished pilot, in six phases. Each phase leaves `npm run check` green and is committed before the next one starts.

When it's done, one command starts a run that works the whole queue, or up to a cap. The UnderCover Agent plans the run as a to-do list that the queue page shows as it changes. It hands each claim to a fresh claim agent, which looks up the sections of the policy wording and the claims manual it needs, decides the claim, and reports back in one line. Failures are put right without anyone stepping in: retries for the model provider, a second try for a claim that fails, a handler for a claim that fails twice, and a check for missed claims before the run ends.

## Approach

The pilot's code organizes the work: a Python loop feeds the agent one claim at a time. The brief asks the agent to organize its own work, so the harness becomes two agents, both built with LangChain's `create_agent` as before:

- **The queue agent** runs the queue. It reads the queue, plans a to-do list, hands claims over one at a time, keeps the list up to date and writes the summary. It never decides a claim itself.
- **The claim agent** works one claim from a clean start, with a new thread and none of the run's history. It is the pilot's agent with new tools for looking things up and new instructions.

The parts that must never go wrong are enforced in code, not left to the model's judgment:

| Rule from the brief | Enforced by |
| --- | --- |
| No claim decided or paid twice | The backend, as in the pilot: a decision needs a claim in progress, and a claim is paid once |
| A claim that fails goes back in the queue, and after two failures is left for a handler | The backend counts attempts. The harness releases a failed claim, and the backend decides where it goes |
| One bad claim never stops the run | `work_claim` catches the failure, releases the claim and reports it in a line |
| The run stays within its cap | `work_claim` refuses a new claim once the cap is reached |
| No missed claims | A completion check, as middleware, stops the queue agent finishing while claims within its cap are still waiting |
| Provider errors and timeouts | LangChain's `ModelRetryMiddleware` on both agents, and a timeout on the model |

The order of the claims, the to-do list and the summary are the agent's own work, as the brief asks.

Choices worth reviewing:

- **Our own `write_todos` tool rather than LangChain's `TodoListMiddleware`.** The middleware keeps the list inside the agent's memory, with three states. The brief needs four states, including "left for a handler", and needs the list in the backend so the dashboard can show it. A tool that calls a backend operation does both.
- **The subagent is a tool, `work_claim`.** Calling it runs a new claim agent to the end and returns one line. That line is built from the claim's record in the backend after the claim agent finishes, so the queue agent learns what was recorded, not what the claim agent says it did.
- **The wording and the manual are stored as numbered sections**, split on their `## N. Title` headings, so the claim agent can list, search and read them one section at a time. Reading a section notes it on the claim, which is how the claim page shows what the agent read.
- **No other agent framework.** Deep Agents from Lab 2 has these pieces ready made, but the brief asks us to build them into our own agent. Everything here is `create_agent`, its built-in middleware, and our tools and backend.

## Design

### How a run works

1. `uv run -m agent --cap 5` releases any claim left in progress by a run that stopped, then starts a run with the backend and the queue agent.
2. The queue agent reads the queue with `list_claims`, writes a to-do list with one item for each claim it means to work, and marks the first one in progress.
3. It calls `work_claim` for that claim. The harness starts the claim, builds a fresh claim agent and runs it. The claim agent's steps are recorded on the claim as they happen, as in the pilot.
4. `work_claim` returns one line. The queue agent ticks off the item and moves on.
5. When the agent tries to finish, the completion check looks for waiting claims within the cap. If there are any, it names them and sends the agent back to work.
6. The agent's final reply is the summary for the handlers. The harness records it with `finish_run` and prints it.

`uv run -m agent` works every waiting claim, with the cap set to the number of claims waiting when it starts. `uv run -m agent CLM-1001` works one claim through `work_claim`, with the same recovery and no run or to-do list.

### Claim states

One new state, for a claim that failed twice:

| State | Meaning | Label on screen | Color |
| --- | --- | --- | --- |
| `waiting` | In the queue, not started | Waiting | Cerulean |
| `in_progress` | A claim agent is working on it | In progress | Marigold |
| `waiting_for_sign_off` | Approved over $1,000, payment held | Waiting for sign-off | Coral |
| `decided` | Decided, and paid where that applies | Decided | Sea Green |
| `left_for_handler` | Failed twice before it was decided | Left for a handler | Raspberry |

A claim now moves `waiting` → `in_progress` → `decided` or `waiting_for_sign_off`, or back to `waiting` after a first failure, or to `left_for_handler` after a second.

### Database

- `claims` gains `attempts`, the number of times the claim has been started.
- `sections`: the document (`policy_wording` or `claims_manual`), the section number, the title and the text. Seeding splits both files on their `## N. Title` headings: 12 sections of the wording and 14 of the manual. The text above the first heading is not a section.
- `reads`: each section the agent read on a claim, with the thread id and time.
- `runs`: the run id (a number), the cap, start and finish times, the summary, and the to-do list as JSON.
- The policy wording is no longer stored whole in `settings`, since nothing serves it whole.

### API

Every operation keeps an `operation_id`, a one-line docstring and no optional inputs. New and changed operations:

| Operation | Route | What it does |
| --- | --- | --- |
| `start_run` | `POST /api/runs` | Body `{cap}`, at least 1. Starts a run with an empty to-do list |
| `write_todos` | `PUT /api/runs/{run_id}/todos` | Body `{todos: [{content, status}]}`. Replaces the run's to-do list. `status` is `todo`, `in_progress`, `done` or `left_for_handler` |
| `finish_run` | `POST /api/runs/{run_id}/finish` | Body `{summary}`. Records the summary and the finish time |
| `list_runs` | `GET /api/runs` | Every run with its to-do list, newest first |
| `release_claim` | `POST /api/claims/{claim_id}/release` | Body `{reason}`. Records the reason as an `error` step, then moves the claim back to `waiting`, or to `left_for_handler` if it has been started twice |
| `list_sections` | `GET /api/sections` | The contents of the wording and the manual: document, number and title |
| `search_sections` | `GET /api/sections/search?query=` | Sections containing any of the query's words, ranked by how many they contain, best five first, each with its matching paragraphs |
| `read_section` | `POST /api/claims/{claim_id}/reads` | Body `{document, section}`. Returns the section in full and notes the read on the claim. A POST, because it records something |
| `get_instructions` | `GET /api/instructions/{agent}` | Changed: `agent` is `queue` or `claim`, and the reply is that agent's instructions alone, without the wording |
| `start_claim` | unchanged route | Now also adds one to `attempts` |
| `get_claim` | unchanged route | Now includes `attempts` and `sections_read`: document, number and title of each section read, in the order first read, without repeats |

Rules the backend enforces, on top of the pilot's:

- `release_claim` needs a claim in progress (409). A decided claim is never released, so it can't be decided again.
- `read_section` needs a claim in progress (409) and a known section (404). `document` must be `policy_wording` or `claims_manual` (422).
- `write_todos` and `finish_run` need a run that hasn't finished (409). A to-do item needs some content (422). Unknown runs return 404.
- The `section` of a decision is now described as "the section of the policy wording or the claims manual relied on".

### The claim agent

- Tools, each named after the backend operation it calls: `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `search_sections`, `read_section`, `record_decision` and `pay_claim`.
- Instructions in `backend/instructions/claim.md`, written from the policy wording and the claims manual, and never from `data/evals/`. They follow the manual's order of work (section 4). They say to look things up rather than recite them: the plan's limits in wording section 1, the benefit's section, the general exclusions, the manual's required documents, its interpretation notes, repeat claims and meals without receipts, and the payout steps. They state the three decisions as the manual does (section 2), including the referral of a third claim in 12 months and of a story the documents contradict. A decision names its source, such as "Policy wording, section 3, Trip Delay" or "Claims manual, section 9, Repeat claims".
- `run(claim_id, thread_id)` stays as in the pilot: start the claim, fetch the instructions, stream the agent and record each step.
- `work_claim(claim_id)` makes one attempt and returns one line:
  - `CLM-1001  approve  $420.00  paid`, `CLM-1002  approve  $1,350.00  waiting for sign-off`, `CLM-1003  refer  $0.00`
  - When the attempt raises, or ends with no decision recorded, and the claim is still in progress, it releases the claim with the reason: `CLM-1004  failed: <reason>. Back in the queue for another try`, or `... Left for a handler` the second time.
  - If the claim was decided before the failure, it isn't released, and the line gives the decision.
  - `CLM-1005  not worked: Claim CLM-1005 is not waiting` when the claim can't be started.

### The queue agent

- Tools: `list_claims` and `write_todos`, named after backend operations, and `work_claim`, which hands a claim to a claim agent. The run id is fixed by the harness, so the model can't write to another run's list.
- `work_claim` counts the claims the run has started. Once the cap is reached it refuses a new one: `CLM-1006  not worked: this run's cap of 5 claims is reached`. A second try at a claim the run already started doesn't count again.
- Instructions in `backend/instructions/queue.md`: read the queue, choose the order, plan one to-do item per claim within the cap, mark each item in progress before handing it over, and mark it done, back to do or left for a handler from the line that comes back. A claim that went back in the queue should be tried again later in the run. Before finishing, read the queue again. End with a short summary for the handlers: what was decided, which payouts wait for sign-off, which claims were left for a handler and why.
- Its first message gives the cap: "Work the queue. You can work up to 5 claims in this run."
- If the queue agent itself fails after its retries, the run is finished with the summary "The run stopped early: <error>", and the command exits with the error. No claim is left in progress, because the queue agent only runs between claims.

### Middleware

| Middleware | On | What it does |
| --- | --- | --- |
| `ModelRetryMiddleware` | Both agents | Retries a failed model call 3 times, waiting 2, 4 and 8 seconds, then raises. It owns retrying, so the model client's own retries are off. The model client has a 120 second timeout, so a hung call becomes an error that is retried |
| `ModelCallLimitMiddleware` | Claim agent | Stops a claim agent after 30 model calls with an error, so an agent stuck in a loop becomes a failed attempt rather than a run that never ends |
| Completion check, our own `after_model` hook | Queue agent | When the model replies without a tool call, meaning it wants to finish, it checks for waiting claims the run should still work: claims it has already tried, and any waiting claim while it is under its cap. If there are any, it adds a message naming them and sends the agent back to the model. It reminds at most 3 times, so a model that won't listen can't loop forever |

The default model becomes `deepseek/deepseek-v4.1-flash` with low reasoning effort. `MODEL_NAME` still overrides it, as before.

### Command line

- `uv run -m agent --cap 5` prints `Working up to 5 claims with deepseek/deepseek-v4.1-flash`, then each line from `work_claim` as it comes back, then the summary.
- `uv run -m agent` does the same with the cap set to the number of waiting claims.
- `uv run -m agent CLM-1001` prints the one line for that claim.

### Dashboard

- **Queue page:** a to-do list panel for the newest run, refreshed every two seconds with the queue. It shows when the run started, its cap, how many items are done, and each item with its status: To do in Cerulean, In progress in Marigold, Done in Sea Green, Left for a handler in Raspberry. When the run finishes it shows the finish time and the summary. Before any run it says "No runs yet". The counts by state gain a fifth tile, Left for a handler.
- **Claim page:** a "Sections read" panel listing each section, such as "Claims manual, 7. Interpretation notes". Error steps show as "Failed". A claim left for a handler says "The agent couldn't finish this claim. It's left for a handler."
- **Instructions page:** two panels, "Running the queue" and "Working a claim", read only. It no longer shows the policy wording, because the agent isn't given it whole.

### Tests

Tests never call a model. The stub model from the pilot gains one ability: an exception in its script is raised in place of a reply, which stands in for a provider error. The queue agent and the claim agents each get their own stub. The retry delay is set to zero in tests.

### How the criteria are checked

As in the pilot: API calls run against `npm run dev` on a freshly seeded database (`uv run -m backend.seed`), and pages are checked in the browser with the Playwright MCP server at `http://localhost:5173`. Only criteria marked "Live" use the real model. Every live run starts from a fresh seed and works at most five claims.

## Phase 1: Attempts, releasing a claim, and runs with a to-do list

Backend only. Add `attempts` and the `left_for_handler` state, `release_claim` and the `error` step kind, and the runs table with `start_run`, `write_todos`, `finish_run` and `list_runs`.

- [x] pytest covers every new rule, including each 404, 409 and 422
- [x] `start_claim` on `CLM-1001`, then `get_claim`, shows `attempts` 1
- [x] `release_claim` on `CLM-1001` with reason "The model provider timed out" returns status `waiting`, and `list_steps` ends with an `error` step carrying that reason
- [x] Starting and releasing `CLM-1001` a second time returns `left_for_handler`. `start_claim` on it then returns 409, and so does `record_decision`
- [x] `release_claim` on a waiting claim, and on a decided claim, each return 409, and the decided claim keeps its decision
- [x] `POST /api/runs` with cap 5 returns run 1 with cap 5, an empty to-do list and no finish time. A cap of 0 returns 422
- [x] `write_todos` with three items, one in each of `todo`, `in_progress` and `done`, then `list_runs`, shows those items in order. A status of `skipped` and an empty content each return 422, and run 99 returns 404
- [x] A second run comes first in `list_runs`
- [x] `finish_run` records the summary and a finish time. Finishing again, and `write_todos` afterwards, each return 409
- [x] The OpenAPI test passes with the new operations
- [x] `npm run check` passes

## Phase 2: The wording and the manual in sections

Backend only. Seed the `sections` table, add `list_sections`, `search_sections` and `read_section`, record reads, and add `sections_read` to `get_claim`.

- [x] `uv run -m backend.seed` prints `Seeded 25 claims, 50 policies, 49 customers, 3 handlers and 26 sections into undercover.db`
- [x] `curl -s localhost:8000/api/sections` returns 26 sections, 12 of `policy_wording` and 14 of `claims_manual`. Wording section 10 is "How we work out your payment" and manual section 9 is "Repeat claims"
- [x] `curl -s "localhost:8000/api/sections/search?query=giraffe"` returns manual section 7, "Interpretation notes", with the paragraph on wild animals. A word that appears nowhere returns an empty list
- [x] `read_section` for wording section 3 on `CLM-1001` after `start_claim` returns "Trip Delay" and its full text. On a waiting claim it returns 409, for section 99 it returns 404, and for the document `brochure` it returns 422
- [x] After reading wording section 3, manual section 10, then wording section 3 again, `get_claim` lists `sections_read` as wording 3 then manual 10, each once
- [x] Each section's text in the database matches the text under its heading in `data/`, checked by a pytest test
- [x] The OpenAPI test passes, and `grep -rn evals backend agent dashboard/src` finds nothing
- [x] `npm run check` passes

## Phase 3: The claim agent

Give the claim agent the section tools, write its instructions from the wording and the manual, serve them from `get_instructions` at `/api/instructions/claim`, and add the default model, the middleware and `work_claim`. The command line works one named claim. The instructions page shows the claim agent's instructions.

- [x] A pytest test checks that the claim agent's tools are exactly `get_claim`, `get_policy`, `get_claim_history`, `list_sections`, `search_sections`, `read_section`, `record_decision` and `pay_claim`, each named after a backend operation
- [x] `curl -s localhost:8000/api/instructions/claim` returns the claim agent's instructions, which name the tools for looking things up and don't contain the wording itself: no `## 10. How we work out your payment`
- [x] A stub model test checks that the system prompt the claim agent receives is the text from `/api/instructions/claim`
- [x] Stub model test: the claim agent searches, reads wording section 3 and manual section 10, approves and pays. The claim is decided and paid, `sections_read` lists both sections, and the steps include the `read_section` calls in order
- [x] Stub model test: a provider error on the first model call is retried, and the claim is decided
- [x] Stub model test: a stub that never stops calling `get_claim` is stopped at 30 model calls, and `work_claim` reports the failure
- [x] Stub model tests for `work_claim`, one for each kind of line: paid, waiting for sign-off, refer, failed and back in the queue (status `waiting`, `attempts` 1, an `error` step), failed a second time and left for a handler, finished without a decision (released), failed after its decision (not released, still decided, the line gives the decision), and not waiting (nothing recorded)
- [x] `main.model()` is `deepseek/deepseek-v4.1-flash` with low reasoning effort and a 120 second timeout, and `openrouter/free` when `MODEL_NAME` says so
- [x] Browser, `/instructions`: the claim agent's instructions, with no text box, input or edit button. The e2e test of the instructions page checks for them
- [x] `grep -rn evals backend agent dashboard/src` finds nothing, and `grep -rn "data/" agent` finds nothing
- [ ] Live: on a fresh database with `npm run dev` running, `uv run -m agent CLM-1005` prints one line with a decision and payout
- [ ] Live: `curl -s localhost:8000/api/claims/CLM-1005` then shows a decision with a section and a reason, and `sections_read` includes at least one section of the claims manual
- [x] `npm run check` passes

## Phase 4: The queue agent

Add the queue agent with `list_claims`, `write_todos` and `work_claim`, the cap, the completion check, the release of claims left in progress, `finish_run`, its instructions at `/api/instructions/queue`, and the `--cap` option. The instructions page shows both sets of instructions.

- [ ] A pytest test checks that the queue agent's tools are exactly `list_claims`, `write_todos` and `work_claim`, and that the first two are named after backend operations
- [ ] Stub model test, the to-do list stored: with three claims waiting, the queue stub writes a to-do list, works each claim and ticks it off, then replies with a summary. `list_runs` shows the run with three items `done`, the summary and a finish time
- [ ] Stub model test, the cap: with three claims waiting and a cap of 2, the stub tries all three. The third gets the cap line and stays `waiting` with `attempts` 0
- [ ] Stub model test, a failed claim doesn't stop the run: the claim agent fails on `CLM-1001` every time, and `CLM-1002` and `CLM-1003` are still decided
- [ ] Stub model test, a failed claim is tried again: `CLM-1001` fails once and is worked again later in the run. It ends decided with `attempts` 2, one `error` step and steps from two thread ids
- [ ] Stub model test, a claim that fails twice: `CLM-1001` ends `left_for_handler`, the line says so, and the run goes on to the other claims
- [ ] Stub model test, the check for missed claims: the stub tries to finish after one of three claims. The queue agent is sent back with a message naming the other two, works them, and finishes. With the cap reached, the same stub finishes without a reminder. A stub that never works the missed claims is reminded 3 times, then the run finishes
- [ ] Stub model test: a claim left in progress before the run starts is released at the start and then worked in the run
- [ ] Stub model test: a queue agent that fails after its retries leaves the run finished with "The run stopped early" and no claim in progress
- [ ] A test of the command line: `--cap 5` starts a run with cap 5, no arguments starts one with the number of waiting claims, and a claim id works that claim alone
- [ ] `curl -s localhost:8000/api/instructions/queue` returns the queue agent's instructions, and the instructions page shows "Running the queue" and "Working a claim"
- [ ] Live: on a fresh database with `npm run dev` running, `uv run -m agent --cap 5` prints the header, five lines and a summary
- [ ] Live: afterwards, `curl -s localhost:8000/api/claims` shows 20 claims `waiting` and none `in_progress`, and `curl -s localhost:8000/api/runs` shows the run finished, with every to-do item `done` or `left_for_handler`
- [ ] `npm run check` passes

## Phase 5: Dashboard: the to-do list, sections read, and claims left for a handler

Add the to-do list panel and the fifth state tile to the queue page, the "Sections read" panel and failed steps to the claim page, and the message for a claim left for a handler.

- [ ] vitest covers the to-do list in each status, a finished run with its summary, "No runs yet", the five state tiles, the sections read panel (empty and with sections), a failed step, and a claim left for a handler, against a stubbed `fetch`
- [ ] e2e, to-do list: the test starts a run and writes a to-do list through the API. Without a reload, the queue page shows the items. After the test marks one done and finishes the run, the page shows it ticked off and the summary
- [ ] e2e, left for a handler: the test starts and releases `CLM-1012` twice. The claim page shows "Left for a handler" and two "Failed" steps with their reasons
- [ ] e2e, sections read: the test starts `CLM-1014` and reads two sections. The claim page lists them under "Sections read" without a reload
- [ ] Browser, with `browser_evaluate`: To do, In progress, Done and Left for a handler have the background colors from the design, as does the Left for a handler state chip
- [ ] Browser: screenshots of the queue page with a to-do list, and a claim page with sections read, in light and dark mode, show rounded panels with no outlines, no one-edge borders and no gradients
- [ ] Browser: `browser_console_messages` shows no errors on any page
- [ ] `npm run check` passes

## Phase 6: A live trial, and the documents

Run the trial the brief describes, watch it in the browser, and bring the documents up to date.

- [ ] Live, in the browser: on a fresh database with `npm run dev` running, open `/` and run `uv run -m agent --cap 5`. Snapshots taken during the run show the to-do list filling in, an item In progress, and items ticked off as Done
- [ ] Live: the run ends with five claims worked and 20 still `waiting`. The queue page shows the finished run and its summary
- [ ] Live, in the browser: each worked claim's page shows its steps, including the `read_section` calls, and its "Sections read". At least one claim lists a section of the claims manual
- [ ] Live: every decision has a section and a reason of two or three sentences. Every approval over $1,000 is `waiting_for_sign_off` with no payment, and every other approval is paid exactly its payout
- [ ] `docs/SPEC.md`: decisions follow the policy wording and the claims manual. The manual is out of "Not for now", and "What the team needs to see" includes the run's to-do list, the sections the agent read, and claims left for a handler
- [ ] `docs/TECH_STACK.md` describes the two agents, the middleware, the default model and the entry points
- [ ] `docs/STATUS.md` describes what's built, how to run a capped run, a full run and a single claim, and the results of the live trial
- [ ] `npm run check` passes

## Not in this plan

- **Other open claims in the claim history.** The manual's repeat-claims rule counts every claim filed in 12 months, "approved, declined or open", but `get_claim_history` returns only the claims in the customer's record, not their other claims in the queue. In today's data only CUS-3005 has two claims in the queue, with none before, so no customer reaches three. Adding the customer's queued claims to the history would close the gap for future data. It's left out because the brief doesn't ask for it, and it's worth a decision.
- **Working claims at the same time.** The queue agent hands over one claim at a time.
- **Handling claims left for a handler from the dashboard.** The dashboard shows them, but deciding them or putting them back in the queue isn't built. Reseeding resets them.
- **Starting a run from the dashboard.** Runs start from the command line, as in the pilot.
- **Paying an approval after a failure.** If a claim fails between its approval and its payment, it stays decided and unpaid. The line and the summary say "not paid", and the claim page shows "Not paid yet". The harness doesn't pay it, since payments are only ever made by the agent's own `pay_claim` call or a handler's sign-off.
- **Scoring the agent against `data/evals/`**, which the process says not to open unless asked.
