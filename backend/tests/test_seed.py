from contextlib import closing

from fastapi.testclient import TestClient

from backend.db import connect
from backend.main import app
from backend.seed import reset

COUNTS = """
SELECT
    (SELECT COUNT(*) FROM claims) AS claims,
    (SELECT COUNT(*) FROM policies) AS policies,
    (SELECT COUNT(*) FROM customers) AS customers,
    (SELECT COUNT(*) FROM decisions) AS decisions,
    (SELECT COUNT(*) FROM payments) AS payments,
    (SELECT COUNT(*) FROM steps) AS steps
"""


def counts() -> dict[str, int]:
    with closing(connect()) as connection:
        return dict(connection.execute(COUNTS).fetchone())


def statuses() -> set[str]:
    with closing(connect()) as connection:
        return {row[0] for row in connection.execute("SELECT status FROM claims")}


def test_seed_loads_the_queue():
    assert counts() == {
        "claims": 25,
        "policies": 50,
        "customers": 49,
        "decisions": 0,
        "payments": 0,
        "steps": 0,
    }
    assert statuses() == {"waiting"}


def test_seed_resets_the_queue():
    with closing(connect()) as connection, connection:
        connection.execute("UPDATE claims SET status = 'decided'")
        connection.execute(
            "INSERT INTO steps (claim_id, thread_id, kind, title, detail, created_at)"
            " VALUES ('CLM-1001', 't', 'message', 'Agent', 'Hi', 'now')"
        )
    assert reset() == "Seeded 25 claims, 50 policies and 49 customers."
    assert statuses() == {"waiting"}
    assert counts()["steps"] == 0


def test_the_claim_record_leaves_its_status_to_the_database():
    with closing(connect()) as connection:
        record = connection.execute(
            "SELECT record FROM claims WHERE claim_id = 'CLM-1001'"
        ).fetchone()[0]
    assert '"status"' not in record


def test_startup_seeds_a_missing_database(database):
    database.unlink()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
    assert database.exists()
    assert counts()["claims"] == 25


def test_startup_keeps_an_existing_database():
    with closing(connect()) as connection, connection:
        connection.execute("UPDATE claims SET status = 'decided'")
    with TestClient(app):
        pass
    assert statuses() == {"decided"}
