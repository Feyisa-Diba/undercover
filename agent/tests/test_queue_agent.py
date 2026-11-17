import sqlite3
from contextlib import closing

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from agent import __main__ as cli
from agent import harness
from agent.tests.stub import StubModel, call, decide, provider_down
from agent.tools import QUEUE_TOOLS

CLAIMS = ["CLM-1001", "CLM-1002", "CLM-1003"]


@pytest.fixture
def three_waiting(database, monkeypatch):
    """Leave only CLM-1001, CLM-1002 and CLM-1003 waiting in the queue."""
    monkeypatch.setenv("MODEL_NAME", "stub-model")
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "UPDATE claims SET status = 'decided'"
            " WHERE claim_id NOT IN ('CLM-1001', 'CLM-1002', 'CLM-1003')"
        )


def todos(*statuses):
    return [
        {"content": f"{claim_id} A claim", "status": status}
        for claim_id, status in zip(CLAIMS, statuses, strict=False)
    ]


def work(claim_id, *statuses):
    """The queue agent's replies to mark a claim in progress and work it."""
    return [
        call("write_todos", todos=todos(*statuses)),
        call("work_claim", claim_id=claim_id),
    ]


def summary(text="Worked the claims."):
    return AIMessage(content=text)


def claims(client):
    return {c["claim_id"]: c for c in client.get("/api/claims").json()}


def reminders(stub):
    return [
        m.text
        for m in stub.prompts[-1]
        if isinstance(m, HumanMessage) and m.text.startswith("Before you finish")
    ]


def test_queue_tools(client):
    names = [t.name for t in QUEUE_TOOLS]
    assert names == ["list_claims", "write_todos", "work_claim"]
    shown = convert_to_openai_tool(QUEUE_TOOLS[2])["function"]["parameters"]
    assert list(shown["properties"]) == ["claim_id"]
    operations = {
        operation["operationId"]
        for path in client.get("/openapi.json").json()["paths"].values()
        for operation in path.values()
    }
    assert {"list_claims", "write_todos"} <= operations


def test_queue_instructions(client):
    text = client.get("/api/instructions/queue").json()["text"]
    assert text.startswith("# Running the queue")
    for name in ("list_claims", "write_todos", "work_claim"):
        assert f"`{name}`" in text


def test_the_run_keeps_its_to_do_list(client, capsys, three_waiting):
    queue = StubModel(
        replies=[
            call("list_claims"),
            call("write_todos", todos=todos("todo", "todo", "todo")),
            *work("CLM-1001", "in_progress", "todo", "todo"),
            *work("CLM-1002", "done", "in_progress", "todo"),
            *work("CLM-1003", "done", "done", "in_progress"),
            call("write_todos", todos=todos("done", "done", "done")),
            summary("Worked 3 claims: 2 approved, 1 referred."),
        ]
    )
    claim = StubModel(
        replies=decide(
            "CLM-1001",
            "approve",
            420.0,
            call("pay_claim", claim_id="CLM-1001", amount=420.0),
        )
        + decide("CLM-1002", "approve", 1350.0)
        + decide("CLM-1003", "refer", 0)
    )
    harness.work_queue(None, queue, claim)

    assert capsys.readouterr().out.splitlines() == [
        "Working up to 3 claims with stub-model",
        "CLM-1001  approve  $420.00  paid",
        "CLM-1002  approve  $1,350.00  waiting for sign-off",
        "CLM-1003  refer  $0.00",
        "",
        "Worked 3 claims: 2 approved, 1 referred.",
    ]
    run = client.get("/api/runs").json()[0]
    assert run["cap"] == 3
    assert run["todos"] == todos("done", "done", "done")
    assert run["summary"] == "Worked 3 claims: 2 approved, 1 referred."
    assert run["finished_at"]
    assert reminders(queue) == []
    assert (
        queue.prompts[0][0].content
        == client.get("/api/instructions/queue").json()["text"]
    )
    assert queue.prompts[0][1].content == (
        "Work the queue. You can work up to 3 claims in this run."
    )


def test_a_bad_to_do_list_is_refused_and_the_run_goes_on(client, three_waiting):
    bad = [{"content": "", "status": "todo"}]
    queue = StubModel(
        replies=[
            call("write_todos", todos=bad),
            call("work_claim", claim_id="CLM-1001"),
            summary(),
        ]
    )
    harness.work_queue(1, queue, StubModel(replies=decide("CLM-1001", "refer", 0)))
    refusal = queue.prompts[1][-1]
    assert isinstance(refusal, ToolMessage)
    assert refusal.text.startswith("Refused with status 422")
    assert client.get("/api/runs").json()[0]["todos"] == []
    assert claims(client)["CLM-1001"]["status"] == "decided"


def test_the_cap(client, capsys, three_waiting):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1001"),
            call("work_claim", claim_id="CLM-1002"),
            call("work_claim", claim_id="CLM-1003"),
            summary(),
        ]
    )
    claim = StubModel(
        replies=decide("CLM-1001", "refer", 0) + decide("CLM-1002", "refer", 0)
    )
    harness.work_queue(2, queue, claim)

    lines = capsys.readouterr().out.splitlines()
    assert lines[3] == "CLM-1003  not worked: this run's cap of 2 claims is reached"
    assert client.get("/api/runs").json()[0]["cap"] == 2
    left = claims(client)["CLM-1003"]
    assert left["status"] == "waiting"
    assert client.get("/api/claims/CLM-1003").json()["attempts"] == 0
    assert reminders(queue) == []


def test_a_claim_that_isnt_waiting_doesnt_count_toward_the_cap(
    client, capsys, three_waiting
):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1004"),
            call("work_claim", claim_id="CLM-9999"),
            call("work_claim", claim_id="CLM-1001"),
            summary(),
        ]
    )
    harness.work_queue(1, queue, StubModel(replies=decide("CLM-1001", "refer", 0)))

    assert capsys.readouterr().out.splitlines()[1:4] == [
        "CLM-1004  not worked: Claim CLM-1004 is not waiting",
        "CLM-9999  not worked: Claim CLM-9999 not found",
        "CLM-1001  refer  $0.00",
    ]
    assert claims(client)["CLM-1001"]["status"] == "decided"


def test_a_failed_claim_is_tried_again_later(client, three_waiting):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1001"),
            call("work_claim", claim_id="CLM-1002"),
            call("work_claim", claim_id="CLM-1003"),
            call("work_claim", claim_id="CLM-1001"),
            summary(),
        ]
    )
    claim = StubModel(
        replies=provider_down()
        + decide("CLM-1002", "refer", 0)
        + decide("CLM-1003", "decline", 0)
        + decide("CLM-1001", "refer", 0)
    )
    harness.work_queue(None, queue, claim)

    assert {c: claims(client)[c]["status"] for c in CLAIMS} == dict.fromkeys(
        CLAIMS, "decided"
    )
    retried = client.get("/api/claims/CLM-1001").json()
    assert retried["attempts"] == 2
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["kind"] for s in steps].count("error") == 1
    assert len({s["thread_id"] for s in steps}) == 2


def test_a_claim_that_fails_twice_is_left_and_the_run_goes_on(
    client, capsys, three_waiting
):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1001"),
            call("work_claim", claim_id="CLM-1001"),
            call("work_claim", claim_id="CLM-1002"),
            call("work_claim", claim_id="CLM-1003"),
            summary(),
        ]
    )
    claim = StubModel(
        replies=provider_down()
        + provider_down()
        + decide("CLM-1002", "refer", 0)
        + decide("CLM-1003", "refer", 0)
    )
    harness.work_queue(None, queue, claim)

    lines = capsys.readouterr().out.splitlines()
    assert lines[2].endswith("Left for a handler")
    statuses = {c: claims(client)[c]["status"] for c in CLAIMS}
    assert statuses == {
        "CLM-1001": "left_for_handler",
        "CLM-1002": "decided",
        "CLM-1003": "decided",
    }
    assert reminders(queue) == []


def test_the_check_for_missed_claims(client, three_waiting):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1001"),
            summary("All done."),
            call("work_claim", claim_id="CLM-1002"),
            call("work_claim", claim_id="CLM-1003"),
            summary("Now all done."),
        ]
    )
    claim = StubModel(
        replies=decide("CLM-1001", "refer", 0)
        + decide("CLM-1002", "refer", 0)
        + decide("CLM-1003", "refer", 0)
    )
    harness.work_queue(None, queue, claim)

    assert reminders(queue) == [
        "Before you finish: these claims are still waiting, and this run can"
        " still work them: CLM-1002, CLM-1003. Work them, then finish."
    ]
    assert all(claims(client)[c]["status"] == "decided" for c in CLAIMS)
    assert client.get("/api/runs").json()[0]["summary"] == "Now all done."


def test_a_claim_back_in_the_queue_counts_as_missed(client, three_waiting):
    queue = StubModel(
        replies=[
            call("work_claim", claim_id="CLM-1001"),
            summary(),
            call("work_claim", claim_id="CLM-1001"),
            summary(),
        ]
    )
    claim = StubModel(replies=provider_down() + decide("CLM-1001", "refer", 0))
    harness.work_queue(1, queue, claim)

    assert reminders(queue) == [
        "Before you finish: these claims are still waiting, and this run can"
        " still work them: CLM-1001. Work them, then finish."
    ]
    assert claims(client)["CLM-1001"]["status"] == "decided"


def test_no_reminder_once_the_cap_is_reached(client, three_waiting):
    queue = StubModel(replies=[call("work_claim", claim_id="CLM-1001"), summary()])
    harness.work_queue(1, queue, StubModel(replies=decide("CLM-1001", "refer", 0)))
    assert reminders(queue) == []
    assert claims(client)["CLM-1002"]["status"] == "waiting"


def test_reminders_stop_after_three(client, three_waiting):
    queue = StubModel(replies=[summary() for _ in range(4)])
    harness.work_queue(None, queue, StubModel(replies=[]))
    assert len(reminders(queue)) == harness.MAX_REMINDERS
    assert len(queue.prompts) == 4
    assert client.get("/api/runs").json()[0]["finished_at"]
    assert all(claims(client)[c]["status"] == "waiting" for c in CLAIMS)


def test_a_claim_left_in_progress_is_released_and_worked(client, three_waiting):
    client.post("/api/claims/CLM-1001/start", json={"thread_id": "stopped-run"})
    queue = StubModel(replies=[call("work_claim", claim_id="CLM-1001"), summary()])
    harness.work_queue(1, queue, StubModel(replies=decide("CLM-1001", "refer", 0)))

    worked = client.get("/api/claims/CLM-1001").json()
    assert worked["status"] == "decided"
    assert worked["attempts"] == 2
    first = client.get("/api/claims/CLM-1001/steps").json()[0]
    assert (first["kind"], first["content"], first["thread_id"]) == (
        "error",
        harness.STOPPED,
        "stopped-run",
    )


def test_a_queue_agent_that_fails_finishes_the_run(client, three_waiting):
    queue = StubModel(
        replies=[call("work_claim", claim_id="CLM-1001"), *provider_down()]
    )
    claim = StubModel(replies=decide("CLM-1001", "refer", 0))
    with pytest.raises(RuntimeError, match="The model provider is down"):
        harness.work_queue(None, queue, claim)

    run = client.get("/api/runs").json()[0]
    assert run["summary"] == (
        "The run stopped early: RuntimeError: The model provider is down"
    )
    assert run["finished_at"]
    assert all(c["status"] != "in_progress" for c in claims(client).values())


def test_nothing_waiting(client, capsys, database):
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("UPDATE claims SET status = 'decided'")
    harness.work_queue(None, StubModel(replies=[]), StubModel(replies=[]))
    assert capsys.readouterr().out == "No claims are waiting\n"
    assert client.get("/api/runs").json() == []


@pytest.mark.parametrize(
    ("args", "cap"), [(["--cap", "5"], 5), ([], None)], ids=["capped", "uncapped"]
)
def test_command_line_works_the_queue(monkeypatch, args, cap):
    runs = []
    monkeypatch.setattr(cli, "work_queue", runs.append)
    cli.main(args)
    assert runs == [cap]
