"""Every tool the two agents use, as thin wrappers over the backend's API.

The claim agent's tools are named after the backend operations they call. The
queue agent's tools reach their run through its context: `write_todos` keeps the
run's to-do list and `work_claim` hands a claim to a claim agent within the cap,
keeping the claim's item on the list in step with the claim.
"""

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langchain.tools import ToolRuntime, tool

from agent import api

ONE_CLAIM_AT_A_TIME = threading.Lock()

TodoStatus = Literal["todo", "in_progress", "done", "left_for_handler"]

# A claim's status, as its item on the to-do list shows it
TODO_STATUS: dict[str, TodoStatus] = {
    "waiting": "todo",
    "in_progress": "in_progress",
    "waiting_for_sign_off": "done",
    "decided": "done",
    "left_for_handler": "left_for_handler",
}


class Todo(TypedDict):
    content: str
    status: TodoStatus


@dataclass
class RunContext:
    """One run of the queue agent, shared by its tools and its middleware."""

    run_id: int
    cap: int
    work_claim: Callable[[str], str]
    todos: list[Todo] = field(default_factory=list)
    started: set[str] = field(default_factory=set)
    reminders: int = 0


def answer[**P](call: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> str:
    """Call the backend for the model: its answer as JSON, or why it refused."""
    try:
        return json.dumps(
            call(*args, **kwargs), ensure_ascii=False, separators=(",", ":")
        )
    except api.Refused as refusal:
        return str(refusal)


@tool
def get_claim(claim_id: str) -> str:
    """Get one claim in full: the story, the items claimed and the documents."""
    return answer(api.get_claim, claim_id)


@tool
def get_policy(policy_id: str) -> str:
    """Get a policy: the plan, add-ons, purchase date, trip and travelers."""
    return answer(api.get_policy, policy_id)


@tool
def get_claim_history(customer_id: str) -> str:
    """Get a customer's earlier claims, with the outcome and the amount paid."""
    return answer(api.get_claim_history, customer_id)


@tool
def list_sections() -> str:
    """List the sections of the policy wording and the claims manual."""
    return answer(api.list_sections)


@tool
def search_sections(query: str) -> str:
    """Find the sections of the wording and the manual that use the query's words."""
    return answer(api.search_sections, query)


@tool
def read_section(
    claim_id: str, document: Literal["policy_wording", "claims_manual"], section: int
) -> str:
    """Read one section of the policy wording or the claims manual in full."""
    return answer(api.read_section, claim_id, document, section)


@tool
def record_decision(
    claim_id: str,
    decision: Literal["approve", "decline", "refer"],
    payout: float,
    section: str,
    reason: str,
) -> str:
    """Record the decision on a claim; an approval over the limit waits for sign-off."""
    return answer(api.record_decision, claim_id, decision, payout, section, reason)


@tool
def pay_claim(claim_id: str, amount: float) -> str:
    """Pay an approved claim its payout, unless it needs a handler's sign-off."""
    return answer(api.pay_claim, claim_id, amount)


@tool
def list_claims() -> str:
    """List every claim in the queue, with its status, decision and payout."""
    return answer(api.list_claims)


@tool
def write_todos(todos: list[Todo], runtime: ToolRuntime[RunContext]) -> str:
    """Replace the run's to-do list: send every item with its status."""
    try:
        api.write_todos(runtime.context.run_id, todos)
    except api.Refused as refusal:
        return str(refusal)
    runtime.context.todos = [todo.copy() for todo in todos]
    return "Saved the to-do list"


def keep_in_step(run: RunContext, claim_id: str, status: TodoStatus) -> None:
    """Show a claim's status on the run's to-do list, if the claim is on it."""
    items = [todo for todo in run.todos if todo["content"].startswith(claim_id)]
    for todo in items:
        todo["status"] = status
    if items:
        api.write_todos(run.run_id, run.todos)


@tool
def work_claim(claim_id: str, runtime: ToolRuntime[RunContext]) -> str:
    """Hand a waiting claim to a claim agent, and get back one line: the
    decision and payout, or what went wrong. The claim's item on the to-do
    list shows it in progress, then where it stands when it comes back."""
    run = runtime.context
    with ONE_CLAIM_AT_A_TIME:  # so the cap holds when calls come in parallel
        if claim_id not in run.started and len(run.started) >= run.cap:
            return (
                f"{claim_id}  not worked: this run's cap of {run.cap} claims is reached"
            )
        keep_in_step(run, claim_id, "in_progress")
        try:
            line = run.work_claim(claim_id)
        except api.Refused as refusal:
            keep_in_step(run, claim_id, "todo")
            return f"{claim_id}  not worked: {refusal.detail}"
        run.started.add(claim_id)
        keep_in_step(run, claim_id, TODO_STATUS[api.get_claim(claim_id)["status"]])
        return line


CLAIM_TOOLS = [
    get_claim,
    get_policy,
    get_claim_history,
    list_sections,
    search_sections,
    read_section,
    record_decision,
    pay_claim,
]

QUEUE_TOOLS = [list_claims, write_todos, work_claim]
