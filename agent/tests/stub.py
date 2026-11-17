from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class StubModel(BaseChatModel):
    """A chat model that gives scripted replies, raises scripted errors in their
    place, and keeps the prompts it was sent."""

    replies: list[Any]
    prompts: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "stub"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.prompts.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


def call(name, text="", **args):
    return AIMessage(
        content=text, tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}]
    )


def decide(claim_id, decision, payout, *extra, section="Section 3, Trip Delay"):
    """The replies of a claim agent that reads the claim and decides it."""
    return [
        call("get_claim", claim_id=claim_id),
        call(
            "record_decision",
            claim_id=claim_id,
            decision=decision,
            payout=payout,
            section=section,
            reason="Covered.",
        ),
        *extra,
        AIMessage(content=f"Decision: {decision}."),
    ]


def provider_down(times=4):
    """Errors for a model call that fails, then fails each of its 3 retries."""
    return [RuntimeError("The model provider is down") for _ in range(times)]
