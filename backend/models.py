"""The shapes the API reads and returns."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

Status = Literal["waiting", "in_progress", "waiting_for_sign_off", "decided"]
DecisionKind = Literal["approve", "decline", "refer"]
StepKind = Literal["call", "result", "message"]


class StartClaim(BaseModel):
    thread_id: str


class NewStep(BaseModel):
    thread_id: str
    kind: StepKind
    title: str
    detail: str


class Step(NewStep):
    step_id: int
    created_at: str


class NewDecision(BaseModel):
    explanation: str
    policy_section: str
    decision: DecisionKind
    payout: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def only_approvals_pay(self) -> Self:
        if self.decision != "approve" and self.payout != 0:
            raise ValueError("A decline or a referral pays $0.00.")
        return self


class NewPayment(BaseModel):
    amount: Annotated[float, Field(gt=0)]


class SignOff(BaseModel):
    handler_id: str


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class Decision(BaseModel):
    decision: DecisionKind
    payout: float
    explanation: str
    policy_section: str
    decided_at: str
    signed_off_by: str | None
    signed_off_at: str | None


class Payment(BaseModel):
    amount: float
    paid_at: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    submitted_on: str
    amount_claimed: float
    status: Status
    decision: DecisionKind | None
    payout: float | None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    story: str
    items: list[Item]
    amount_claimed: float
    documents: list[Document]
    status: Status
    thread_id: str | None
    decision: Decision | None
    payment: Payment | None


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: Trip
    travelers: list[str]
    status: str


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class ClaimHistory(BaseModel):
    customer_id: str
    name: str
    customer_since: str
    previous_claims: list[PreviousClaim]


class PolicyWording(BaseModel):
    version: str
    text: str


class Instructions(BaseModel):
    text: str


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool
