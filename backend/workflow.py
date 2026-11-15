"""The operations that move a claim along, and the rules that govern them."""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from backend.db import Db
from backend.models import (
    Claim,
    NewDecision,
    NewPayment,
    NewStep,
    SignOff,
    StartClaim,
    Step,
)
from backend.records import APPROVAL_LIMIT, HANDLERS, find_claim, load_claim, money

router = APIRouter(prefix="/api/claims/{claim_id}")


def now() -> str:
    """The time now in UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@router.post("/start", operation_id="start_claim")
def start_claim(claim_id: str, body: StartClaim, db: Db) -> Claim:
    """Mark a claim as in progress for an agent run."""
    if find_claim(db, claim_id)["status"] not in {"waiting", "in_progress"}:
        raise HTTPException(409, f"Claim {claim_id} already has a decision.")
    db.execute(
        "UPDATE claims SET status = 'in_progress', thread_id = ? WHERE claim_id = ?",
        (body.thread_id, claim_id),
    )
    return load_claim(db, claim_id)


@router.post("/steps", operation_id="add_step")
def add_step(claim_id: str, body: NewStep, db: Db) -> Step:
    """Record one step the agent took on a claim."""
    find_claim(db, claim_id)
    row = db.execute(
        "INSERT INTO steps (claim_id, thread_id, kind, title, detail, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?) RETURNING *",
        (claim_id, body.thread_id, body.kind, body.title, body.detail, now()),
    ).fetchone()
    return Step(**dict(row))


@router.get("/steps", operation_id="list_steps")
def list_steps(claim_id: str, db: Db) -> list[Step]:
    """List the steps the agent took on a claim, in order."""
    find_claim(db, claim_id)
    rows = db.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY step_id", (claim_id,)
    )
    return [Step(**dict(row)) for row in rows]


@router.post("/decision", operation_id="record_decision")
def record_decision(claim_id: str, body: NewDecision, db: Db) -> Claim:
    """Record the agent's decision on a claim in progress."""
    row = find_claim(db, claim_id)
    if row["status"] != "in_progress":
        message = (
            "isn't in progress"
            if row["status"] == "waiting"
            else "already has a decision"
        )
        raise HTTPException(409, f"Claim {claim_id} {message}.")
    claimed = json.loads(row["record"])["amount_claimed"]
    if body.payout > claimed:
        raise HTTPException(
            422, f"A payout can't be more than the amount claimed, {money(claimed)}."
        )
    over_limit = body.decision == "approve" and body.payout > APPROVAL_LIMIT
    db.execute(
        "INSERT INTO decisions (claim_id, decision, payout, explanation,"
        " policy_section, decided_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            body.decision,
            round(body.payout, 2),
            body.explanation,
            body.policy_section,
            now(),
        ),
    )
    db.execute(
        "UPDATE claims SET status = ? WHERE claim_id = ?",
        ("waiting_for_sign_off" if over_limit else "decided", claim_id),
    )
    return load_claim(db, claim_id)


def payment_refusal(claim: Claim, amount: float) -> str | None:
    """Say why a payment can't be made, or None when it can."""
    decision = claim.decision
    if decision is None or decision.decision != "approve":
        return f"Claim {claim.claim_id} has no approved payout to pay."
    if claim.status == "waiting_for_sign_off":
        return f"Payment of {money(decision.payout)} needs a handler's sign-off."
    if claim.payment:
        return f"Claim {claim.claim_id} has already been paid."
    if round(amount, 2) != decision.payout:
        return f"The approved payout is {money(decision.payout)}, not {money(amount)}."
    return None


@router.post("/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, body: NewPayment, db: Db) -> Claim:
    """Pay an approved claim its approved payout."""
    refusal = payment_refusal(load_claim(db, claim_id), body.amount)
    if refusal:
        raise HTTPException(409, refusal)
    db.execute(
        "INSERT INTO payments VALUES (?, ?, ?)",
        (claim_id, round(body.amount, 2), now()),
    )
    return load_claim(db, claim_id)


@router.post("/sign-off", operation_id="sign_off")
def sign_off(claim_id: str, body: SignOff, db: Db) -> Claim:
    """Sign off a payout over the approval limit, which releases the payment."""
    claim = load_claim(db, claim_id)
    if claim.status != "waiting_for_sign_off" or claim.decision is None:
        raise HTTPException(409, f"Claim {claim_id} isn't waiting for sign-off.")
    handler = HANDLERS.get(body.handler_id)
    if handler is None:
        raise HTTPException(404, f"Handler {body.handler_id} not found")
    if not handler.can_approve_over_limit:
        raise HTTPException(
            403, f"{handler.name} can't sign off payouts over {money(APPROVAL_LIMIT)}."
        )
    signed_off_at = now()
    db.execute(
        "UPDATE decisions SET signed_off_by = ?, signed_off_at = ? WHERE claim_id = ?",
        (handler.handler_id, signed_off_at, claim_id),
    )
    db.execute(
        "INSERT INTO payments VALUES (?, ?, ?)",
        (claim_id, claim.decision.payout, signed_off_at),
    )
    db.execute("UPDATE claims SET status = 'decided' WHERE claim_id = ?", (claim_id,))
    return load_claim(db, claim_id)
