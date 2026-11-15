"""The UnderCover backend."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.db import Db, database_path
from backend.models import (
    Claim,
    ClaimHistory,
    ClaimSummary,
    Handler,
    Instructions,
    Policy,
    PolicyWording,
)
from backend.records import COMPANY, HANDLERS, POLICY_WORDING, find, load_claim
from backend.seed import reset
from backend.workflow import router

INSTRUCTIONS = Path(__file__).with_name("instructions.md")

QUEUE = """
SELECT
    c.claim_id,
    json_extract(cu.record, '$.name') AS customer_name,
    json_extract(c.record, '$.claim_type') AS claim_type,
    json_extract(c.record, '$.submitted_on') AS submitted_on,
    json_extract(c.record, '$.amount_claimed') AS amount_claimed,
    c.status,
    d.decision,
    d.payout
FROM claims c
JOIN customers cu USING (customer_id)
LEFT JOIN decisions d USING (claim_id)
ORDER BY c.claim_id
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Seed the database on the first start, when there is none yet."""
    if not database_path().exists():
        print(reset())
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)
app.include_router(router)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List the claims queue with where each claim stands."""
    return [ClaimSummary(**dict(row)) for row in db.execute(QUEUE)]


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Get a claim in full, with its status, decision and payment."""
    return load_claim(db, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, db: Db) -> Policy:
    """Get a policy: its plan, add-ons, purchase date, trip and travelers."""
    query = "SELECT record FROM policies WHERE policy_id = ?"
    return Policy(**json.loads(find(db, query, "Policy", policy_id)["record"]))


@app.get("/api/customers/{customer_id}/history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, db: Db) -> ClaimHistory:
    """Get a customer's earlier claims, without their contact details."""
    query = "SELECT record FROM customers WHERE customer_id = ?"
    record = json.loads(find(db, query, "Customer", customer_id)["record"])
    return ClaimHistory(**record)


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> PolicyWording:
    """Get the policy wording that decisions follow."""
    return PolicyWording(version=COMPANY["policy_wording_version"], text=POLICY_WORDING)


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Instructions:
    """Get the agent's instructions, read only."""
    return Instructions(text=INSTRUCTIONS.read_text(encoding="utf-8"))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers."""
    return list(HANDLERS.values())
