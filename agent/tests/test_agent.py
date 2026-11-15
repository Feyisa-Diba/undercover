from itertools import count

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

from agent import main

ids = count()


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def calls(*tool_calls: tuple[str, dict]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call-{next(ids)}"}
            for name, args in tool_calls
        ],
    )


def decision(choice: str, payout: float) -> AIMessage:
    args = {
        "explanation": "The wording covers it.",
        "policy_section": "Section 3, Trip Delay",
        "decision": choice,
        "payout": payout,
    }
    return calls(("record_decision", args))


READ = calls(("get_claim", {}), ("get_policy", {}), ("get_claim_history", {}))


def work(claim_id: str, *replies: AIMessage) -> str:
    return main.run(claim_id, "thread-1", StubModel(messages=iter(replies)))


def claim(claim_id: str) -> dict:
    return main.fetch("GET", f"/api/claims/{claim_id}")


def steps(claim_id: str) -> list[dict]:
    return main.fetch("GET", f"/api/claims/{claim_id}/steps")


def test_approve_and_pay_under_the_limit():
    reply = work(
        "CLM-1001",
        READ,
        decision("approve", 420),
        calls(("pay_claim", {"amount": 420})),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert reply == "Approved and paid $420.00."
    result = claim("CLM-1001")
    assert result["status"] == "decided"
    assert result["thread_id"] == "thread-1"
    assert result["payment"]["amount"] == 420.0
    recorded = steps("CLM-1001")
    kinds = [(s["kind"], s["title"]) for s in recorded]
    reads = ["get_claim", "get_policy", "get_claim_history"]
    assert kinds[:3] == [("call", name) for name in reads]
    # The three reads run in parallel, so their results arrive in any order.
    results = {s["title"]: s["detail"] for s in recorded[3:6]}
    assert set(results) == set(reads)
    assert {kind for kind, _ in kinds[3:6]} == {"result"}
    assert kinds[6:] == [
        ("call", "record_decision"),
        ("result", "record_decision"),
        ("call", "pay_claim"),
        ("result", "pay_claim"),
        ("message", "Agent"),
    ]
    assert "Meridian Air" in results["get_claim"]
    assert "premium" in results["get_policy"]
    assert "CLM-0412" in results["get_claim_history"]
    assert {s["thread_id"] for s in recorded} == {"thread-1"}


def test_a_payment_over_the_limit_is_blocked():
    work(
        "CLM-1003",
        READ,
        decision("approve", 1500),
        calls(("pay_claim", {"amount": 1500})),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    result = claim("CLM-1003")
    assert result["status"] == "waiting_for_sign_off"
    assert result["payment"] is None
    payment = steps("CLM-1003")[-2]
    assert payment["kind"] == "result"
    assert "needs a handler's sign-off" in payment["detail"]


def test_decline():
    work("CLM-1001", READ, decision("decline", 0), AIMessage(content="Declined."))
    result = claim("CLM-1001")
    assert result["status"] == "decided"
    assert result["decision"]["decision"] == "decline"
    assert result["decision"]["payout"] == 0.0
    assert result["payment"] is None


def test_a_refusal_comes_back_to_the_agent():
    work(
        "CLM-1001",
        READ,
        decision("approve", 9999),
        decision("approve", 420),
        AIMessage(content="Approved."),
    )
    refusal = steps("CLM-1001")[7]
    assert "more than the amount claimed" in refusal["detail"]
    assert claim("CLM-1001")["decision"]["payout"] == 420.0


def test_the_tools_are_bound_to_the_claim():
    tools = main.claim_tools(
        {"claim_id": "CLM-1001", "policy_id": "POL-2001", "customer_id": "CUS-3001"}
    )
    assert [t.name for t in tools] == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "record_decision",
        "pay_claim",
    ]
    for t in tools:
        assert not {"claim_id", "policy_id", "customer_id"} & set(t.args)
    assert list(tools[3].args) == [
        "explanation",
        "policy_section",
        "decision",
        "payout",
    ]


def test_the_system_prompt_holds_the_instructions_and_the_wording():
    prompt = main.system_prompt()
    assert prompt.startswith("# The UnderCover Agent")
    assert "The policy wording follows.\n\n# UnderCover Travel Insurance" in prompt
    assert "## 10. How we work out your payment" in prompt


def test_steps_of_a_message_with_text_and_calls():
    message = AIMessage(
        content="Reading the claim.",
        tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}],
    )
    assert main.steps(message) == [
        ("message", "Agent", "Reading the claim."),
        ("call", "get_claim", "{}"),
    ]
    result = ToolMessage(content="{}", tool_call_id="1", name="get_claim")
    assert main.steps(result) == [("result", "get_claim", "{}")]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().max_retries == main.MAX_RETRIES
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
