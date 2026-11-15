"""Work the claims queue: uv run -m agent, or uv run -m agent CLM-1001 for one claim."""

import sys
import uuid

from agent.main import fetch, run


def outcome(claim_id: str) -> str:
    """Say where a claim stands, in one line."""
    claim = fetch("GET", f"/api/claims/{claim_id}")
    decision = claim["decision"]
    if decision is None:
        return f"{claim_id}  {claim['status']}  no decision"
    payout = f"${decision['payout']:,.2f}"
    return f"{claim_id}  {claim['status']}  {decision['decision']}  {payout}"


def main(claim_ids: list[str]) -> None:
    """Work the claims given, or every waiting claim when none are."""
    if not claim_ids:
        queue = fetch("GET", "/api/claims")
        claim_ids = [c["claim_id"] for c in queue if c["status"] == "waiting"]
    for claim_id in claim_ids:
        run(claim_id, uuid.uuid4().hex)
        print(outcome(claim_id), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
