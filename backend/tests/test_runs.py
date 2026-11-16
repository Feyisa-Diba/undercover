import pytest

TODOS = [
    {"content": "CLM-1001 Trip delay in Rome", "status": "done"},
    {"content": "CLM-1002 Lost suitcase", "status": "in_progress"},
    {"content": "CLM-1003 Medical bill", "status": "todo"},
]


def start_run(client, cap=5):
    return client.post("/api/runs", json={"cap": cap})


def write(client, run_id, todos):
    return client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})


def finish(client, run_id, summary="Worked 3 claims."):
    return client.post(f"/api/runs/{run_id}/finish", json={"summary": summary})


def test_start_run(client):
    response = start_run(client)
    assert response.status_code == 200
    run = response.json()
    assert run["run_id"] == 1
    assert run["cap"] == 5
    assert run["todos"] == []
    assert run["finished_at"] is None
    assert run["summary"] is None
    assert run["started_at"]


@pytest.mark.parametrize("cap", [0, -1])
def test_a_run_needs_a_cap_of_at_least_one(client, cap):
    assert start_run(client, cap).status_code == 422


def test_write_todos(client):
    start_run(client)
    response = write(client, 1, TODOS)
    assert response.status_code == 200
    assert response.json()["todos"] == TODOS
    assert client.get("/api/runs").json()[0]["todos"] == TODOS

    left = [{"content": "CLM-1001 Trip delay", "status": "left_for_handler"}]
    assert write(client, 1, left).json()["todos"] == left


@pytest.mark.parametrize(
    "todo",
    [
        {"content": "CLM-1001", "status": "skipped"},
        {"content": "", "status": "todo"},
    ],
)
def test_invalid_todos(client, todo):
    start_run(client)
    assert write(client, 1, [todo]).status_code == 422


def test_unknown_run(client):
    assert write(client, 99, TODOS).status_code == 404
    assert finish(client, 99).status_code == 404


def test_newest_run_first(client):
    start_run(client, 5)
    start_run(client, 25)
    assert [run["run_id"] for run in client.get("/api/runs").json()] == [2, 1]


def test_no_runs_yet(client):
    assert client.get("/api/runs").json() == []


def test_finish_run(client):
    start_run(client)
    response = finish(client, 1, "Worked 3 claims: 2 approved, 1 referred.")
    assert response.status_code == 200
    assert response.json()["summary"] == "Worked 3 claims: 2 approved, 1 referred."
    assert response.json()["finished_at"]

    again = finish(client, 1)
    assert again.status_code == 409
    assert again.json()["detail"] == "Run 1 has finished"
    assert write(client, 1, TODOS).status_code == 409


def test_finish_needs_a_summary(client):
    start_run(client)
    assert finish(client, 1, "").status_code == 422
