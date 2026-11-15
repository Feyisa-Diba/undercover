"""Lookups shared by the API's operations."""

import json
import sqlite3

from fastapi import HTTPException

from backend.db import DATA, read_json
from backend.models import Claim, Decision, Handler, Payment

COMPANY = read_json("company.json")
APPROVAL_LIMIT: float = COMPANY["payout_approval_limit"]
HANDLERS = {h["handler_id"]: Handler(**h) for h in read_json("handlers.json")}
POLICY_WORDING = (DATA / "policy_wording.md").read_text(encoding="utf-8")


def money(amount: float) -> str:
    """Format an amount in US dollars, such as $1,250.00."""
    return f"${amount:,.2f}"


def find(db: sqlite3.Connection, query: str, label: str, key: str) -> sqlite3.Row:
    """Fetch the one row a query finds by its id, or answer 404."""
    row = db.execute(query, (key,)).fetchone()
    if row is None:
        raise HTTPException(404, f"{label} {key} not found")
    return row


def find_claim(db: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Fetch a claim's row, or answer 404."""
    return find(db, "SELECT * FROM claims WHERE claim_id = ?", "Claim", claim_id)


def load_claim(db: sqlite3.Connection, claim_id: str) -> Claim:
    """Load a claim in full, with its status, decision and payment."""
    row = find_claim(db, claim_id)
    decision = db.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    payment = db.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    return Claim(
        **json.loads(row["record"]),
        status=row["status"],
        thread_id=row["thread_id"],
        decision=Decision(**dict(decision)) if decision else None,
        payment=Payment(**dict(payment)) if payment else None,
    )
