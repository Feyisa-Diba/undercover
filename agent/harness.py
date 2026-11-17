"""The UnderCover Agent's harness: the model, the middleware and running the agents.

The queue agent plans a run as a to-do list and hands each claim to a claim agent,
which works that one claim from a clean start. The harness puts problems right: it
retries failed model calls, stops a claim agent that loops, releases a claim that
fails, and sends the queue agent back to work if it misses a claim.
"""

import json
import os
import uuid
from collections.abc import Callable
from functools import partial
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
    after_model,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import SecretStr

from agent import api
from agent.tools import CLAIM_TOOLS, QUEUE_TOOLS, RunContext

load_dotenv(override=True)

OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT = 120
MODEL_RETRIES = 3
RETRY_DELAY = 2.0
MAX_MODEL_CALLS = 30
MAX_REMINDERS = 3
NO_DECISION = "The agent finished without recording a decision"
STOPPED = "The run working this claim stopped before it finished"

Agent = CompiledStateGraph[Any, Any, Any, Any]


def model_name() -> str:
    """Return the model in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    return os.getenv("MODEL_NAME") or DEFAULT_MODEL


def chat_model() -> ChatOpenAI:
    """Return the model on OpenRouter, with low reasoning effort for the default."""
    return ChatOpenAI(
        model=model_name(),
        base_url=OPENROUTER_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if os.getenv("MODEL_NAME") else "low",
        timeout=MODEL_TIMEOUT,
        max_retries=0,
    )


def retries() -> ModelRetryMiddleware:
    """Retry a failed model call, waiting longer each time, then raise."""
    return ModelRetryMiddleware(
        max_retries=MODEL_RETRIES, initial_delay=RETRY_DELAY, on_failure="error"
    )


def run_agent(
    agent: Agent,
    prompt: str,
    on_message: Callable[[AnyMessage], None],
    context: RunContext | None = None,
) -> str:
    """Run an agent on a prompt, pass on each message it adds, and return its reply."""
    messages: list[AnyMessage] = [HumanMessage(prompt)]
    for state in agent.stream(
        {"messages": messages}, context=context, stream_mode="values"
    ):
        for message in state["messages"][len(messages) :]:
            on_message(message)
        messages = state["messages"]
    return messages[-1].text


def claim_agent(model: BaseChatModel) -> Agent:
    """Build a claim agent, which stops after MAX_MODEL_CALLS model calls."""
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        retries(),
        ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="error"),
    ]
    return create_agent(
        model,
        tools=CLAIM_TOOLS,
        system_prompt=api.get_instructions("claim"),
        middleware=middleware,
    )


def steps(message: AnyMessage) -> list[tuple[str, str]]:
    """Turn one message from an agent's run into steps for the dashboard."""
    if isinstance(message, ToolMessage):
        return [("tool_result", f"{message.name}: {message.text}")]
    found = []
    if message.text:
        found.append(("message", message.text))
    if isinstance(message, AIMessage):
        for call in message.tool_calls:
            args = ", ".join(f"{k}={json.dumps(v)}" for k, v in call["args"].items())
            found.append(("tool_call", f"{call['name']}({args})"))
    return found


def record_steps(claim_id: str, message: AnyMessage) -> None:
    """Record a message from the claim agent as steps on its claim."""
    for kind, content in steps(message):
        api.record_step(claim_id, kind, content)


def work_claim(claim_id: str, model: BaseChatModel | None = None) -> str:
    """Work one claim with a fresh claim agent, and report back in one line.

    Raises api.Refused if the claim can't be started, such as when it isn't waiting.
    """
    api.start_claim(claim_id, str(uuid.uuid4()))
    try:
        agent = claim_agent(model or chat_model())
        run_agent(agent, f"Claim {claim_id}", partial(record_steps, claim_id))
    except Exception as error:  # one failed claim must never stop the run
        return settle(
            claim_id, f"{type(error).__name__}: {' '.join(str(error).split())}"
        )
    return settle(claim_id, NO_DECISION)


def settle(claim_id: str, failure: str) -> str:
    """Report how a claim ended, releasing it with the failure if it's in progress."""
    claim = api.get_claim(claim_id)
    if claim["status"] != "in_progress":
        return outcome(claim)
    reason = failure.rstrip(". ")
    released = api.release_claim(claim_id, reason)
    if released["status"] == "waiting":
        return f"{claim_id}  failed: {reason}. Back in the queue for another try"
    return f"{claim_id}  failed: {reason}. Left for a handler"


def outcome(claim: api.Json) -> str:
    """Describe a decided claim in one line: the decision, payout and payment."""
    decision = claim["decision"]
    line = f"{claim['claim_id']}  {decision['decision']}  ${decision['payout']:,.2f}"
    if claim["payment"]:
        return f"{line}  paid"
    if claim["status"] == "waiting_for_sign_off":
        return f"{line}  waiting for sign-off"
    if decision["decision"] == "approve":
        return f"{line}  not paid"
    return line


def missed_claims(run: RunContext) -> list[str]:
    """Return the waiting claims the run could still work, retries first."""
    waiting = [c["claim_id"] for c in api.list_claims() if c["status"] == "waiting"]
    again = [claim_id for claim_id in waiting if claim_id in run.started]
    new = [claim_id for claim_id in waiting if claim_id not in run.started]
    room = max(run.cap - len(run.started), 0)
    return again + new[:room]


@after_model(can_jump_to=["model"])
def check_for_missed_claims(
    state: AgentState[Any], runtime: Runtime[RunContext]
) -> dict[str, Any] | None:
    """Send the queue agent back to work if it finishes with claims it could work."""
    last = state["messages"][-1]
    run = runtime.context
    if not isinstance(last, AIMessage) or last.tool_calls:
        return None
    if run.reminders >= MAX_REMINDERS:
        return None
    missed = missed_claims(run)
    if not missed:
        return None
    run.reminders += 1
    reminder = (
        "Before you finish: these claims are still waiting, and this run can"
        f" still work them: {', '.join(missed)}. Work them, then finish."
    )
    return {"messages": [HumanMessage(reminder)], "jump_to": "model"}


def queue_agent(model: BaseChatModel) -> Agent:
    """Build the queue agent, with the run's context for its tools."""
    return create_agent(
        model,
        tools=QUEUE_TOOLS,
        system_prompt=api.get_instructions("queue"),
        middleware=[retries(), check_for_missed_claims],
        context_schema=RunContext,
    )


def print_line(message: AnyMessage) -> None:
    """Print each claim's line as it comes back to the queue agent."""
    if isinstance(message, ToolMessage) and message.name == "work_claim":
        print(message.text, flush=True)


def release_stopped_claims() -> None:
    """Release any claim left in progress by a run that stopped."""
    for claim in api.list_claims():
        if claim["status"] == "in_progress":
            api.release_claim(claim["claim_id"], STOPPED)


def work_queue(
    cap: int | None = None,
    model: BaseChatModel | None = None,
    claim_model: BaseChatModel | None = None,
) -> None:
    """Run the queue agent on the waiting claims, up to the cap."""
    release_stopped_claims()
    waiting = sum(claim["status"] == "waiting" for claim in api.list_claims())
    if not waiting:
        print("No claims are waiting")
        return
    started = api.start_run(cap or waiting)
    run = RunContext(
        started["run_id"], started["cap"], partial(work_claim, model=claim_model)
    )
    print(f"Working up to {run.cap} claims with {model_name()}", flush=True)
    prompt = f"Work the queue. You can work up to {run.cap} claims in this run."
    try:
        summary = run_agent(queue_agent(model or chat_model()), prompt, print_line, run)
    except Exception as error:
        api.finish_run(
            run.run_id, f"The run stopped early: {type(error).__name__}: {error}"
        )
        raise
    api.finish_run(run.run_id, summary)
    print(f"\n{summary}")
