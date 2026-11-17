import pytest
from fastapi.testclient import TestClient

from agent import api, harness
from backend.main import app
from backend.tests.conftest import client, database

__all__ = ["client", "database"]


@pytest.fixture(autouse=True)
def backend(monkeypatch):
    """Send the agent's requests to the test backend, and retry without waiting."""
    monkeypatch.setattr(
        api, "client", lambda: TestClient(app, base_url="http://testserver/api")
    )
    monkeypatch.setattr(harness, "RETRY_DELAY", 0)
