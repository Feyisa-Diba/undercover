"""The backend's API: every call the agents make, one function per operation."""

from typing import Any, Literal

import httpx

BASE_URL = "http://localhost:8000/api"
TIMEOUT = 30

Json = dict[str, Any]


class Refused(Exception):
    """The backend refused a request, with the status code and its reason."""

    def __init__(self, status: int, detail: Any) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"Refused with status {status}: {detail}")


def client() -> httpx.Client:
    """Return a client for the backend's API."""
    return httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)


def call(method: str, path: str, **request: Any) -> Any:
    """Send one request to the backend and return its JSON, or raise Refused."""
    with client() as http:
        response = http.request(method, path, **request)
    if response.is_error:
        raise Refused(response.status_code, response.json()["detail"])
    return response.json()


def list_claims() -> list[Json]:
    """List every claim in the queue."""
    return call("GET", "/claims")


def get_claim(claim_id: str) -> Json:
    """Get one claim in full."""
    return call("GET", f"/claims/{claim_id}")


def get_policy(policy_id: str) -> Json:
    """Get a policy."""
    return call("GET", f"/policies/{policy_id}")


def get_claim_history(customer_id: str) -> list[Json]:
    """Get a customer's earlier claims."""
    return call("GET", f"/customers/{customer_id}/claims")


def list_sections() -> list[Json]:
    """List the sections of the policy wording and the claims manual."""
    return call("GET", "/sections")


def search_sections(query: str) -> list[Json]:
    """Find the sections that use the query's words."""
    return call("GET", "/sections/search", params={"query": query})


def read_section(claim_id: str, document: str, section: int) -> Json:
    """Read one section in full, noting the read on the claim."""
    body = {"document": document, "section": section}
    return call("POST", f"/claims/{claim_id}/reads", json=body)


def record_decision(
    claim_id: str, decision: str, payout: float, section: str, reason: str
) -> Json:
    """Record the decision on a claim."""
    body = {
        "decision": decision,
        "payout": payout,
        "section": section,
        "reason": reason,
    }
    return call("POST", f"/claims/{claim_id}/decision", json=body)


def pay_claim(claim_id: str, amount: float) -> Json:
    """Pay an approved claim."""
    return call("POST", f"/claims/{claim_id}/payment", json={"amount": amount})


def start_claim(claim_id: str, thread_id: str) -> Json:
    """Start work on a waiting claim."""
    return call("POST", f"/claims/{claim_id}/start", json={"thread_id": thread_id})


def release_claim(claim_id: str, reason: str) -> Json:
    """Put a failed claim back in the queue, or leave it for a handler."""
    return call("POST", f"/claims/{claim_id}/release", json={"reason": reason})


def record_step(claim_id: str, kind: str, content: str) -> Json:
    """Record one step of the agent's work on a claim."""
    body = {"kind": kind, "content": content}
    return call("POST", f"/claims/{claim_id}/steps", json=body)


def get_instructions(agent: Literal["queue", "claim"]) -> str:
    """Get one agent's instructions."""
    return call("GET", f"/instructions/{agent}")["text"]


def start_run(cap: int) -> Json:
    """Start a run of the queue agent."""
    return call("POST", "/runs", json={"cap": cap})


def write_todos(run_id: int, todos: list[Any]) -> Json:
    """Replace a run's to-do list."""
    return call("PUT", f"/runs/{run_id}/todos", json={"todos": todos})


def finish_run(run_id: int, summary: str) -> Json:
    """Finish a run with its summary."""
    return call("POST", f"/runs/{run_id}/finish", json={"summary": summary})
