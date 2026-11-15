"""Reset the database to the claims queue: uv run -m backend.seed"""

from contextlib import closing

from backend.db import connect, seed


def reset() -> str:
    """Seed the database and say what went in."""
    with closing(connect()) as connection, connection:
        claims, policies, customers = seed(connection)
    return f"Seeded {claims} claims, {policies} policies and {customers} customers."


if __name__ == "__main__":
    print(reset())
