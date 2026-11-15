import pytest

from backend.seed import reset


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    """Give each test a freshly seeded database of its own."""
    path = tmp_path / "undercover.db"
    monkeypatch.setenv("UNDERCOVER_DB", str(path))
    reset()
    return path
