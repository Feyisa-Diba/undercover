"""The UnderCover Agent's queue agent, which hands each claim to a claim agent."""

import threading
from typing import Any, Literal, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, after_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime

from agent import main
from agent.main import NOT_WORKED, call_backend, model, model_name, retries
from agent.tools import list_claims, reply, request

MAX_REMINDERS = 3
STOPPED = "The run working this claim stopped before it finished"


class Todo(TypedDict):
    content: str
    status: Literal["todo", "in_progress", "done", "left_for_handler"]


class QueueRun:
    """One run of the queue agent: its cap and the claims it has started."""

    def __init__(self, run_id: int, cap: int, claim_llm: BaseChatModel | None) -> None:
        self.run_id = run_id
        self.cap = cap
        self.claim_llm = claim_llm
        self.started: set[str] = set()
        self.reminders = 0
        self.lock = threading.Lock()

    def tools(self) -> list[BaseTool]:
        """The queue agent's tools, with the run's id fixed so it can't be changed."""

        @tool
        def write_todos(todos: list[Todo]) -> str:
            """Replace the run's to-do list: send every item with its status."""
            path = f"/api/runs/{self.run_id}/todos"
            response = request("PUT", path, {"todos": todos})
            return reply(response) if response.is_error else "Saved the to-do list"

        @tool
        def work_claim(claim_id: str) -> str:
            """Hand a waiting claim to a claim agent, and get back one line: the
            decision and payout, or what went wrong."""
            with self.lock:
                return self.work(claim_id)

        return [list_claims, write_todos, work_claim]

    def work(self, claim_id: str) -> str:
        """Work one claim within the run's cap, and print its line."""
        if claim_id not in self.started and len(self.started) >= self.cap:
            line = (
                f"{claim_id}  {NOT_WORKED}: this run's cap of {self.cap} claims"
                " is reached"
            )
        else:
            line = main.work_claim(claim_id, self.claim_llm)
            if f"  {NOT_WORKED}: " not in line:
                self.started.add(claim_id)
        print(line, flush=True)
        return line

    def missed(self) -> list[str]:
        """Return the waiting claims the run should still work: retries first."""
        waiting = [
            claim["claim_id"]
            for claim in call_backend("GET", "/api/claims")
            if claim["status"] == "waiting"
        ]
        retries = [claim_id for claim_id in waiting if claim_id in self.started]
        room = max(self.cap - len(self.started), 0)
        others = [claim_id for claim_id in waiting if claim_id not in self.started]
        return retries + others[:room]


def completion_check(run: QueueRun) -> AgentMiddleware[Any, Any, Any]:
    """Send the queue agent back to work if it tries to finish with claims missed."""

    @after_model(can_jump_to=["model"])
    def check_for_missed_claims(
        state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if run.reminders >= MAX_REMINDERS:
            return None
        missed = run.missed()
        if not missed:
            return None
        run.reminders += 1
        reminder = (
            "Before you finish: these claims are still waiting, and this run can"
            f" still work them: {', '.join(missed)}. Work them, then finish."
        )
        return {"messages": [HumanMessage(reminder)], "jump_to": "model"}

    return check_for_missed_claims


def release_stopped_claims() -> None:
    """Release any claim left in progress by a run that stopped."""
    for claim in call_backend("GET", "/api/claims"):
        if claim["status"] == "in_progress":
            path = f"/api/claims/{claim['claim_id']}/release"
            call_backend("POST", path, {"reason": STOPPED})


def work_queue(
    cap: int | None = None,
    llm: BaseChatModel | None = None,
    claim_llm: BaseChatModel | None = None,
) -> None:
    """Run the queue agent on the waiting claims, up to the cap."""
    release_stopped_claims()
    claims = call_backend("GET", "/api/claims")
    waiting = sum(claim["status"] == "waiting" for claim in claims)
    if not waiting:
        print("No claims are waiting")
        return
    cap = cap or waiting
    run_id = call_backend("POST", "/api/runs", {"cap": cap})["run_id"]
    run = QueueRun(run_id, cap, claim_llm)
    print(f"Working up to {cap} claims with {model_name()}", flush=True)
    agent = create_agent(
        llm or model(),
        tools=run.tools(),
        system_prompt=call_backend("GET", "/api/instructions/queue")["text"],
        middleware=[retries(), completion_check(run)],
        checkpointer=InMemorySaver(),
    )
    start = f"Work the queue. You can work up to {cap} claims in this run."
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": start}]},
            config={"configurable": {"thread_id": f"run-{run_id}"}},
        )
    except Exception as error:
        summary = f"The run stopped early: {type(error).__name__}: {error}"
        call_backend("POST", f"/api/runs/{run_id}/finish", {"summary": summary})
        raise
    summary = result["messages"][-1].text
    call_backend("POST", f"/api/runs/{run_id}/finish", {"summary": summary})
    print(f"\n{summary}")
