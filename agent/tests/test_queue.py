import sqlite3
from contextlib import closing

import pytest

from agent import __main__ as cli
from agent import main
from agent.tests.stub import StubModel, call, decide


@pytest.fixture
def three_waiting(database):
    """Leave only CLM-1001, CLM-1002 and CLM-1003 waiting in the queue."""
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "UPDATE claims SET status = 'decided'"
            " WHERE claim_id NOT IN ('CLM-1001', 'CLM-1002', 'CLM-1003')"
        )


def test_work_queue_prints_a_line_per_claim(monkeypatch, capsys, three_waiting):
    stub = StubModel(
        replies=decide(
            "CLM-1001",
            "approve",
            420.0,
            call("pay_claim", claim_id="CLM-1001", amount=420.0),
        )
        + decide("CLM-1002", "approve", 1350.0)
        + decide("CLM-1003", "refer", 0)
    )
    real_work_claim = main.work_claim
    monkeypatch.setattr(
        main, "work_claim", lambda claim_id: real_work_claim(claim_id, stub)
    )
    cli.main([])
    assert capsys.readouterr().out.splitlines() == [
        "CLM-1001  approve  $420.00  paid",
        "CLM-1002  approve  $1,350.00  waiting for sign-off",
        "CLM-1003  refer  $0.00",
    ]
