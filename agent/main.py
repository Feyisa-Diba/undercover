"""The UnderCover Agent's claim agent, which works one claim from a clean start."""

import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from agent.tools import CLAIM_TOOLS, request

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT = 120
MODEL_RETRIES = 3
RETRY_DELAY = 2.0
MAX_MODEL_CALLS = 30


def model_name() -> str:
    """Return the model in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    return os.getenv("MODEL_NAME") or DEFAULT_MODEL


def model() -> ChatOpenAI:
    """Return the model on OpenRouter, with low reasoning effort for the default."""
    return ChatOpenAI(
        model=model_name(),
        base_url=OPENROUTER_BASE_URL,
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


class BackendError(Exception):
    """The backend refused a request the agent's run depends on."""


def call_backend(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend and return its JSON, raising if it refuses."""
    response = request(method, path, body)
    if response.is_error:
        raise BackendError(f"{response.status_code}: {response.json()['detail']}")
    return response.json()


def steps(message: AnyMessage) -> list[tuple[str, str]]:
    """Turn one message from the agent's run into steps for the dashboard."""
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


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work a started claim with a fresh claim agent, recording each step."""
    instructions = call_backend("GET", "/api/instructions/claim")["text"]
    middleware: list[AgentMiddleware[Any, Any, Any]] = [
        retries(),
        ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="error"),
    ]
    agent = create_agent(
        llm or model(),
        tools=CLAIM_TOOLS,
        system_prompt=instructions,
        middleware=middleware,
        checkpointer=InMemorySaver(),
    )
    states = agent.stream(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="values",
    )
    messages = next(states)["messages"]
    for state in states:
        for message in state["messages"][len(messages) :]:
            for kind, content in steps(message):
                call_backend(
                    "POST",
                    f"/api/claims/{claim_id}/steps",
                    {"kind": kind, "content": content},
                )
        messages = state["messages"]
    return messages[-1].text


def work_claim(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim from a clean start and report back in one line."""
    thread_id = str(uuid.uuid4())
    started = request("POST", f"/api/claims/{claim_id}/start", {"thread_id": thread_id})
    if started.is_error:
        return f"{claim_id}  not worked: {started.json()['detail']}"
    try:
        run(claim_id, thread_id, llm)
    except Exception as error:  # one failed claim must never stop the run
        return settle(
            claim_id, f"{type(error).__name__}: {' '.join(str(error).split())}"
        )
    return settle(claim_id, "The agent finished without recording a decision")


def settle(claim_id: str, failure: str) -> str:
    """Report how a claim ended, releasing it if it's still in progress."""
    claim = call_backend("GET", f"/api/claims/{claim_id}")
    if claim["status"] == "in_progress":
        reason = failure.rstrip(". ")
        claim = call_backend(
            "POST", f"/api/claims/{claim_id}/release", {"reason": reason}
        )
        if claim["status"] == "waiting":
            return f"{claim_id}  failed: {reason}. Back in the queue for another try"
        return f"{claim_id}  failed: {reason}. Left for a handler"
    return outcome(claim)


def outcome(claim: dict[str, Any]) -> str:
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


def work_queue() -> None:
    """Work every waiting claim in queue order, printing a line for each."""
    for claim in call_backend("GET", "/api/claims"):
        if claim["status"] == "waiting":
            print(work_claim(claim["claim_id"]), flush=True)
