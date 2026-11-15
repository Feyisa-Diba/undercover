"""The UnderCover database and the business data it starts from."""

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCHEMA = """
DROP TABLE IF EXISTS steps;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS decisions;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS policies;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    record TEXT NOT NULL
);

CREATE TABLE policies (
    policy_id TEXT PRIMARY KEY,
    record TEXT NOT NULL
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies,
    customer_id TEXT NOT NULL REFERENCES customers,
    record TEXT NOT NULL,
    status TEXT NOT NULL,
    thread_id TEXT
);

CREATE TABLE decisions (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    decision TEXT NOT NULL,
    payout REAL NOT NULL,
    explanation TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    signed_off_by TEXT,
    signed_off_at TEXT
);

CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY REFERENCES claims,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);

CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims,
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def database_path() -> Path:
    """Return the database file: UNDERCOVER_DB if set, else undercover.db."""
    return Path(os.environ.get("UNDERCOVER_DB", ROOT / "undercover.db"))


def connect() -> sqlite3.Connection:
    """Open the database, with rows that read like dicts."""
    connection = sqlite3.connect(database_path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def session() -> Iterator[sqlite3.Connection]:
    """Give a request its own connection, committed when the request succeeds."""
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


Db = Annotated[sqlite3.Connection, Depends(session)]


def read_json(name: str) -> Any:
    """Read a JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed(connection: sqlite3.Connection) -> tuple[int, int, int]:
    """Reset the database to the claims queue in data/, every claim waiting."""
    connection.executescript(SCHEMA)
    customers = read_json("customers.json")
    policies = read_json("policies.json")
    claims = read_json("claims.json")
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?)",
        [(c["customer_id"], json.dumps(c)) for c in customers],
    )
    connection.executemany(
        "INSERT INTO policies VALUES (?, ?)",
        [(p["policy_id"], json.dumps(p)) for p in policies],
    )
    connection.executemany(
        "INSERT INTO claims VALUES (?, ?, ?, ?, 'waiting', NULL)",
        [
            (
                c["claim_id"],
                c["policy_id"],
                c["customer_id"],
                json.dumps({k: v for k, v in c.items() if k != "status"}),
            )
            for c in claims
        ],
    )
    return len(claims), len(policies), len(customers)
