from backend.tests.test_workflow import decide, start


def release(client, claim_id, reason="The model provider timed out"):
    return client.post(f"/api/claims/{claim_id}/release", json={"reason": reason})


def test_start_counts_attempts(client):
    assert client.get("/api/claims/CLM-1001").json()["attempts"] == 0
    start(client, "CLM-1001")
    assert client.get("/api/claims/CLM-1001").json()["attempts"] == 1


def test_a_first_failure_goes_back_in_the_queue(client):
    start(client, "CLM-1001")
    response = release(client, "CLM-1001")
    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert (steps[-1]["kind"], steps[-1]["content"]) == (
        "error",
        "The model provider timed out",
    )
    assert steps[-1]["thread_id"] == "t-1"


def test_a_second_failure_is_left_for_a_handler(client):
    start(client, "CLM-1001")
    release(client, "CLM-1001")
    start(client, "CLM-1001")
    response = release(client, "CLM-1001", "The agent stopped without a decision")
    assert response.json()["status"] == "left_for_handler"
    assert response.json()["attempts"] == 2
    assert start(client, "CLM-1001").status_code == 409
    assert decide(client, "CLM-1001", "refer", 0).status_code == 409
    queue = {c["claim_id"]: c for c in client.get("/api/claims").json()}
    assert queue["CLM-1001"]["status"] == "left_for_handler"
    errors = [
        s["content"]
        for s in client.get("/api/claims/CLM-1001/steps").json()
        if s["kind"] == "error"
    ]
    assert errors == [
        "The model provider timed out",
        "The agent stopped without a decision",
    ]


def test_release_needs_a_claim_in_progress(client):
    response = release(client, "CLM-1001")
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is not in progress"
    start(client, "CLM-1001")
    decide(client, "CLM-1001", "refer", 0)
    assert release(client, "CLM-1001").status_code == 409
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "refer"


def test_release_needs_a_reason_and_a_known_claim(client):
    start(client, "CLM-1001")
    assert release(client, "CLM-1001", "").status_code == 422
    assert release(client, "CLM-9999").status_code == 404
