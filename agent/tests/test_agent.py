import pytest
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent import __main__ as cli
from agent import main
from agent.tests.stub import StubModel, call, decide, provider_down
from agent.tools import CLAIM_TOOLS


def steps_of(client, claim_id):
    return client.get(f"/api/claims/{claim_id}/steps").json()


def test_claim_tools_are_named_after_backend_operations(client):
    operations = {
        operation["operationId"]
        for path in client.get("/openapi.json").json()["paths"].values()
        for operation in path.values()
    }
    names = [t.name for t in CLAIM_TOOLS]
    assert names == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "list_sections",
        "search_sections",
        "read_section",
        "record_decision",
        "pay_claim",
    ]
    assert set(names) <= operations


def test_claim_instructions(client):
    text = client.get("/api/instructions/claim").json()["text"]
    assert text.startswith("# Working a claim")
    for name in ("list_sections", "search_sections", "read_section"):
        assert f"`{name}`" in text
    assert "## 10. How we work out your payment" not in text
    assert client.get("/api/instructions/brochure").status_code == 422


def test_the_claim_agent_uses_the_instructions_from_the_backend(client):
    stub = StubModel(replies=decide("CLM-1003", "refer", 0))
    main.work_claim("CLM-1003", stub)
    system = stub.prompts[0][0]
    assert isinstance(system, SystemMessage)
    assert system.content == client.get("/api/instructions/claim").json()["text"]


def test_the_claim_agent_looks_things_up_decides_and_pays(client):
    stub = StubModel(
        replies=[
            call("get_claim", claim_id="CLM-1001"),
            call("get_policy", policy_id="POL-2001"),
            call("get_claim_history", customer_id="CUS-3001"),
            call("list_sections"),
            call("search_sections", query="meals without receipts"),
            call(
                "read_section",
                claim_id="CLM-1001",
                document="policy_wording",
                section=3,
            ),
            call(
                "read_section",
                claim_id="CLM-1001",
                document="claims_manual",
                section=10,
            ),
            call(
                "record_decision",
                claim_id="CLM-1001",
                decision="approve",
                payout=420.0,
                section="Policy wording, section 3, Trip Delay",
                reason="The delay was covered.",
            ),
            call("pay_claim", text="Paying now.", claim_id="CLM-1001", amount=420.0),
            AIMessage(content="Approved and paid $420.00."),
        ]
    )
    assert main.work_claim("CLM-1001", stub) == "CLM-1001  approve  $420.00  paid"

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["attempts"] == 1
    assert claim["payment"]["amount"] == 420.0
    assert claim["sections_read"] == [
        {"document": "policy_wording", "section": 3, "title": "Trip Delay"},
        {"document": "claims_manual", "section": 10, "title": "Meals without receipts"},
    ]

    steps = steps_of(client, "CLM-1001")
    assert [s["kind"] for s in steps] == [
        *(["tool_call", "tool_result"] * 8),
        "message",
        "tool_call",
        "tool_result",
        "message",
    ]
    calls = [s["content"] for s in steps if s["kind"] == "tool_call"]
    assert calls[5:7] == [
        'read_section(claim_id="CLM-1001", document="policy_wording", section=3)',
        'read_section(claim_id="CLM-1001", document="claims_manual", section=10)',
    ]
    assert steps[11]["content"].startswith('read_section: {"document":"policy_wording"')
    assert steps[-1]["content"] == "Approved and paid $420.00."
    assert len({s["thread_id"] for s in steps}) == 1


def test_payment_over_the_limit_is_refused(client):
    stub = StubModel(
        replies=decide(
            "CLM-1002",
            "approve",
            1350.0,
            call("pay_claim", claim_id="CLM-1002", amount=1350.0),
        )
    )
    line = main.work_claim("CLM-1002", stub)
    assert line == "CLM-1002  approve  $1,350.00  waiting for sign-off"

    refusal = stub.prompts[-1][-1]
    assert isinstance(refusal, ToolMessage)
    assert refusal.text.startswith("Refused with status 403")
    assert "needs a handler's sign-off" in refusal.text
    assert client.get("/api/claims/CLM-1002").json()["payment"] is None


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_declines_and_referrals(client, decision):
    stub = StubModel(replies=decide("CLM-1003", decision, 0))
    assert main.work_claim("CLM-1003", stub) == f"CLM-1003  {decision}  $0.00"
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["payment"] is None


def test_an_approval_that_wasnt_paid(client):
    stub = StubModel(replies=decide("CLM-1001", "approve", 420.0))
    assert main.work_claim("CLM-1001", stub) == "CLM-1001  approve  $420.00  not paid"


def test_a_provider_error_is_retried(client):
    replies = decide("CLM-1003", "refer", 0)
    stub = StubModel(replies=[RuntimeError("502 Bad Gateway"), *replies])
    assert main.work_claim("CLM-1003", stub) == "CLM-1003  refer  $0.00"
    assert len(stub.prompts) == len(replies) + 1
    assert [s["kind"] for s in steps_of(client, "CLM-1003")].count("error") == 0


def test_a_failed_claim_goes_back_in_the_queue(client):
    stub = StubModel(replies=provider_down())
    assert main.work_claim("CLM-1001", stub) == (
        "CLM-1001  failed: RuntimeError: The model provider is down."
        " Back in the queue for another try"
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["attempts"] == 1
    last = steps_of(client, "CLM-1001")[-1]
    assert (last["kind"], last["content"]) == (
        "error",
        "RuntimeError: The model provider is down",
    )


def test_a_claim_that_fails_twice_is_left_for_a_handler(client):
    main.work_claim("CLM-1001", StubModel(replies=provider_down()))
    line = main.work_claim("CLM-1001", StubModel(replies=provider_down()))
    assert line == (
        "CLM-1001  failed: RuntimeError: The model provider is down. Left for a handler"
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "left_for_handler"
    assert claim["attempts"] == 2
    steps = steps_of(client, "CLM-1001")
    assert [s["kind"] for s in steps] == ["error", "error"]
    assert steps[0]["thread_id"] != steps[1]["thread_id"]


def test_finishing_without_a_decision_is_a_failure(client):
    stub = StubModel(replies=[AIMessage(content="I am not sure what to do.")])
    assert main.work_claim("CLM-1001", stub) == (
        "CLM-1001  failed: The agent finished without recording a decision."
        " Back in the queue for another try"
    )
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"


def test_a_failure_after_the_decision_keeps_the_decision(client):
    replies = decide("CLM-1003", "refer", 0)[:2]
    stub = StubModel(replies=[*replies, *provider_down()])
    assert main.work_claim("CLM-1003", stub) == "CLM-1003  refer  $0.00"
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["attempts"] == 1
    assert "error" not in [s["kind"] for s in steps_of(client, "CLM-1003")]


def test_a_claim_agent_that_loops_is_stopped(client):
    stub = StubModel(
        replies=[call("get_claim", claim_id="CLM-1001") for _ in range(40)]
    )
    line = main.work_claim("CLM-1001", stub)
    assert line.startswith("CLM-1001  failed: ModelCallLimitExceededError")
    assert line.endswith("Back in the queue for another try")
    assert len(stub.prompts) == main.MAX_MODEL_CALLS


def test_a_claim_that_isnt_waiting_isnt_worked(client):
    main.work_claim("CLM-1003", StubModel(replies=decide("CLM-1003", "refer", 0)))
    before = steps_of(client, "CLM-1003")
    stub = StubModel(replies=[])
    assert main.work_claim("CLM-1003", stub) == (
        "CLM-1003  not worked: Claim CLM-1003 is not waiting"
    )
    assert stub.prompts == []
    assert steps_of(client, "CLM-1003") == before
    assert client.get("/api/claims/CLM-1003").json()["attempts"] == 1
    assert main.work_claim("CLM-9999", stub) == (
        "CLM-9999  not worked: Claim CLM-9999 not found"
    )


def test_command_line_works_one_claim(monkeypatch, capsys):
    monkeypatch.setattr(cli, "work_claim", lambda claim_id: f"{claim_id}  refer  $0.00")
    cli.main(["CLM-1001"])
    assert capsys.readouterr().out == "CLM-1001  refer  $0.00\n"


def test_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = main.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    assert default.request_timeout == 120
    assert default.max_retries == 0
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
    assert main.model().reasoning_effort is None
