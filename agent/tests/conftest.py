import pytest
from fastapi.testclient import TestClient

from agent import main
from backend.main import app
from backend.seed import reset


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give each test a freshly seeded database, reached through the real API."""
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "undercover.db"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    reset()
