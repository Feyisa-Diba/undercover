from agent import __main__ as cli
from agent import main


def approve(claim_id: str, payout: float) -> None:
    main.fetch("POST", f"/api/claims/{claim_id}/start", {"thread_id": "t"})
    body = {
        "explanation": "Covered.",
        "policy_section": "Section 3, Trip Delay",
        "decision": "approve",
        "payout": payout,
    }
    main.fetch("POST", f"/api/claims/{claim_id}/decision", body)


def test_works_every_waiting_claim(monkeypatch, capsys):
    approve("CLM-1001", 420)
    worked = []
    monkeypatch.setattr(cli, "run", lambda claim_id, thread_id: worked.append(claim_id))
    cli.main([])
    assert worked == [f"CLM-{n}" for n in range(1002, 1026)]
    assert capsys.readouterr().out.splitlines()[0] == "CLM-1002  waiting  no decision"


def test_works_one_claim(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run", lambda claim_id, thread_id: approve(claim_id, 1500))
    cli.main(["CLM-1003"])
    assert capsys.readouterr().out == (
        "CLM-1003  waiting_for_sign_off  approve  $1,500.00\n"
    )
