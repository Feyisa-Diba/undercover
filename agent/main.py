"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://127.0.0.1:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> httpx.Response:
    """Call the backend and return its response, refusals included."""
    with backend() as client:
        return client.request(method, path, json=body)


def fetch(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend and return its JSON, raising if it refuses."""
    response = request(method, path, body)
    response.raise_for_status()
    return response.json()


def claim_tools(claim: dict[str, Any]) -> list[BaseTool]:
    """Build the agent's tools, each bound to the one claim it's working."""
    claim_path = f"/api/claims/{claim['claim_id']}"

    @tool
    def get_claim() -> str:
        """Read the claim: the customer's story, the items claimed and the documents."""
        return request("GET", claim_path).text

    @tool
    def get_policy() -> str:
        """Read the customer's policy: plan, add-ons, purchase date, trip, travelers."""
        return request("GET", f"/api/policies/{claim['policy_id']}").text

    @tool
    def get_claim_history() -> str:
        """Read the customer's earlier claims with UnderCover."""
        return request("GET", f"/api/customers/{claim['customer_id']}/history").text

    @tool(parse_docstring=True)
    def record_decision(
        explanation: str,
        policy_section: str,
        decision: Literal["approve", "decline", "refer"],
        payout: float,
    ) -> str:
        """Record your decision on the claim. You can record it only once.

        Args:
            explanation: Two or three plain sentences explaining the decision.
            policy_section: The section of the wording it rests on, such as
                "Section 3, Trip Delay".
            decision: approve, decline or refer.
            payout: The amount to pay in US dollars, or 0 to decline or refer.
        """
        body = {
            "explanation": explanation,
            "policy_section": policy_section,
            "decision": decision,
            "payout": payout,
        }
        return request("POST", f"{claim_path}/decision", body).text

    @tool(parse_docstring=True)
    def pay_claim(amount: float) -> str:
        """Pay the customer the payout you approved.

        Args:
            amount: The approved payout in US dollars.
        """
        return request("POST", f"{claim_path}/payment", {"amount": amount}).text

    return [get_claim, get_policy, get_claim_history, record_decision, pay_claim]


def system_prompt() -> str:
    """Join the agent's instructions and the policy wording, both from the backend."""
    instructions = fetch("GET", "/api/instructions")["text"]
    wording = fetch("GET", "/api/policy-wording")["text"]
    return f"{instructions}\n{wording}"


def steps(message: AnyMessage) -> list[tuple[str, str, str]]:
    """Turn one message of the run into steps for the dashboard: kind, title, detail."""
    if isinstance(message, ToolMessage):
        return [("result", message.name or "tool", str(message.text))]
    found = [("message", "Agent", str(message.text))] if message.text else []
    if isinstance(message, AIMessage):
        found += [
            ("call", c["name"], json.dumps(c["args"])) for c in message.tool_calls
        ]
    return found


def report(claim_id: str, thread_id: str, message: AnyMessage) -> None:
    """Post a message's steps to the backend, where the dashboard shows them."""
    for kind, title, detail in steps(message):
        step = {"thread_id": thread_id, "kind": kind, "title": title, "detail": detail}
        fetch("POST", f"/api/claims/{claim_id}/steps", step)


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one claim, reporting each step to the backend, and return the last reply."""
    claim = fetch("POST", f"/api/claims/{claim_id}/start", {"thread_id": thread_id})
    agent = create_agent(
        llm or model(), tools=claim_tools(claim), system_prompt=system_prompt()
    )
    updates = agent.stream(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    )
    reply = ""
    for update in updates:
        for node in update.values():
            for message in node["messages"]:
                report(claim_id, thread_id, message)
                reply = str(message.text) if isinstance(message, AIMessage) else reply
    return reply
