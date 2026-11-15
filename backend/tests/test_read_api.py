from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_list_claims():
    claims = client.get("/api/claims").json()
    assert [c["claim_id"] for c in claims] == [f"CLM-{n}" for n in range(1001, 1026)]
    assert {c["status"] for c in claims} == {"waiting"}
    assert {c["decision"] for c in claims} == {None}
    assert {c["payout"] for c in claims} == {None}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "customer_name": "Maya Patel",
        "claim_type": "trip_delay",
        "submitted_on": "2026-06-24",
        "amount_claimed": 420.0,
        "status": "waiting",
        "decision": None,
        "payout": None,
    }


def test_get_claim():
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["amount_claimed"] == 420.0
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["story"].startswith("My flight home from Rome")
    assert claim["status"] == "waiting"
    assert claim["thread_id"] is None
    assert claim["decision"] is None
    assert claim["payment"] is None


def test_get_claim_not_found():
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Claim CLM-9999 not found"}


def test_get_policy():
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["trip"]["departs_on"] == "2026-06-10"
    assert policy["trip"]["returns_on"] == "2026-06-18"
    assert policy["trip"]["trip_cost"] == 3100.0
    assert policy["travelers"] == ["Maya Patel"]


def test_get_policy_not_found():
    response = client.get("/api/policies/POL-9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Policy POL-9999 not found"}


def test_get_claim_history():
    history = client.get("/api/customers/CUS-3001/history").json()
    assert history["name"] == "Maya Patel"
    assert history["customer_since"] == "2023-04-11"
    assert [c["claim_id"] for c in history["previous_claims"]] == ["CLM-0412"]
    for private in ("email", "phone", "address", "date_of_birth"):
        assert private not in history


def test_get_claim_history_not_found():
    response = client.get("/api/customers/CUS-9999/history")
    assert response.status_code == 404
    assert response.json() == {"detail": "Customer CUS-9999 not found"}


def test_get_policy_wording():
    wording = client.get("/api/policy-wording").json()
    assert wording["version"] == "2026.1"
    assert wording["text"].startswith("# UnderCover Travel Insurance: Policy Wording")


def test_list_handlers():
    handlers = client.get("/api/handlers").json()
    assert [h["name"] for h in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]
    assert "email" not in handlers[0]


def test_get_instructions():
    text = client.get("/api/instructions").json()["text"]
    assert text.startswith("# The UnderCover Agent")
    assert text.endswith("The policy wording follows.\n")
