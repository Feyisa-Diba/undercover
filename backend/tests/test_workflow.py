import pytest
from fastapi.testclient import TestClient

from backend import workflow
from backend.main import app
from backend.models import Handler

client = TestClient(app)


def start(claim_id: str, thread_id: str = "thread-1"):
    return client.post(f"/api/claims/{claim_id}/start", json={"thread_id": thread_id})


def decide(claim_id: str, decision: str, payout: float):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "explanation": "The reasons.",
            "policy_section": "Section 3, Trip Delay",
            "decision": decision,
            "payout": payout,
        },
    )


def pay(claim_id: str, amount: float):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign(claim_id: str, handler_id: str = "HND-01"):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def approved(claim_id: str, payout: float):
    start(claim_id)
    return decide(claim_id, "approve", payout)


def test_start_claim():
    claim = start("CLM-1001").json()
    assert claim["status"] == "in_progress"
    assert claim["thread_id"] == "thread-1"


def test_restart_a_claim_in_progress():
    start("CLM-1001")
    assert start("CLM-1001", "thread-2").json()["thread_id"] == "thread-2"


def test_start_a_decided_claim():
    approved("CLM-1001", 420)
    response = start("CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 already has a decision."


def test_start_an_unknown_claim():
    assert start("CLM-9999").status_code == 404


def test_steps_are_listed_in_order():
    for n in range(3):
        step = {"thread_id": "t", "kind": "call", "title": f"s{n}", "detail": "{}"}
        assert client.post("/api/claims/CLM-1001/steps", json=step).status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["title"] for s in steps] == ["s0", "s1", "s2"]
    assert steps[0]["kind"] == "call"
    assert steps[0]["created_at"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_a_step_needs_a_known_kind():
    step = {"thread_id": "t", "kind": "guess", "title": "x", "detail": ""}
    assert client.post("/api/claims/CLM-1001/steps", json=step).status_code == 422


def test_steps_of_an_unknown_claim():
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404


def test_decide_a_claim_that_is_not_started():
    response = decide("CLM-1001", "approve", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 isn't in progress."


def test_approve_under_the_limit():
    claim = approved("CLM-1001", 420).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "approve"
    assert claim["decision"]["payout"] == 420.0
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"] is None
    queue = client.get("/api/claims").json()
    assert queue[0]["decision"] == "approve"
    assert queue[0]["payout"] == 420.0


def test_approve_exactly_the_limit_goes_straight_through():
    assert approved("CLM-1003", 1000).json()["status"] == "decided"
    assert pay("CLM-1003", 1000).json()["payment"]["amount"] == 1000.0


def test_approve_over_the_limit_waits_for_sign_off():
    assert approved("CLM-1003", 1000.01).json()["status"] == "waiting_for_sign_off"
    response = pay("CLM-1003", 1000.01)
    assert response.status_code == 409
    assert (
        response.json()["detail"] == "Payment of $1,000.01 needs a handler's sign-off."
    )


def test_decline():
    start("CLM-1001")
    claim = decide("CLM-1001", "decline", 0).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 0.0


@pytest.mark.parametrize(
    ("decision", "payout"), [("decline", 10), ("refer", 5), ("approve", -1)]
)
def test_payouts_that_do_not_fit_the_decision(decision, payout):
    start("CLM-1001")
    assert decide("CLM-1001", decision, payout).status_code == 422


def test_a_payout_over_the_amount_claimed():
    response = approved("CLM-1001", 420.01)
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "A payout can't be more than the amount claimed, $420.00."
    )


def test_decide_twice():
    approved("CLM-1001", 420)
    response = decide("CLM-1001", "approve", 300)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 already has a decision."


def test_pay_an_approved_claim():
    approved("CLM-1001", 420)
    claim = pay("CLM-1001", 420).json()
    assert claim["payment"]["amount"] == 420.0
    assert claim["payment"]["paid_at"]


def test_pay_before_a_decision():
    start("CLM-1001")
    response = pay("CLM-1001", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 has no approved payout to pay."


def test_pay_a_declined_claim():
    start("CLM-1001")
    decide("CLM-1001", "decline", 0)
    assert pay("CLM-1001", 420).status_code == 409


def test_pay_a_different_amount():
    approved("CLM-1001", 300)
    response = pay("CLM-1001", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "The approved payout is $300.00, not $420.00."


def test_pay_twice():
    approved("CLM-1001", 420)
    pay("CLM-1001", 420)
    response = pay("CLM-1001", 420)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 has already been paid."


def test_sign_off_releases_the_payment():
    approved("CLM-1003", 1500)
    claim = sign("CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["signed_off_by"] == "HND-01"
    assert claim["decision"]["signed_off_at"]
    assert claim["payment"]["amount"] == 1500.0
    assert pay("CLM-1003", 1500).status_code == 409


def test_sign_off_a_claim_that_is_not_waiting():
    approved("CLM-1001", 420)
    response = sign("CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 isn't waiting for sign-off."


def test_sign_off_by_an_unknown_handler():
    approved("CLM-1003", 1500)
    response = sign("CLM-1003", "HND-99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Handler HND-99 not found"


def test_sign_off_by_a_handler_who_cannot_approve_over_the_limit(monkeypatch):
    trainee = Handler(
        handler_id="HND-09",
        name="Sam Lee",
        role="Trainee",
        can_approve_over_limit=False,
    )
    monkeypatch.setitem(workflow.HANDLERS, "HND-09", trainee)
    approved("CLM-1003", 1500)
    response = sign("CLM-1003", "HND-09")
    assert response.status_code == 403
    assert response.json()["detail"] == "Sam Lee can't sign off payouts over $1,000.00."
    assert client.get("/api/claims/CLM-1003").json()["payment"] is None
