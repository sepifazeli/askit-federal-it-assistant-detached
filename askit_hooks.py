"""Code-level guardrails for AskIT.

The system prompt tells the model to search the Knowledge Base before answering any
policy question, but a prompt is an instruction, not a guarantee. RequireRetrievalHook
enforces it in code: a policy question that is answered without a successful
`retrieve` call has its answer rejected and the agent is asked to retrieve and answer
again. If it still has not retrieved after `max_retries` attempts, the user gets a
fixed fallback message instead of an answer from general knowledge.
"""
import logging
import re

from strands.hooks import (
    AfterInvocationEvent,
    AfterToolCallEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)

logger = logging.getLogger(__name__)

# Topics the system prompt calls "policy", plus the phrasings people use to ask about them.
# Deliberately broad: a false positive costs one extra retrieve call, a false negative
# falls back to the prompt instruction.
POLICY_PATTERN = re.compile(
    r"\b(?:"
    r"polic(?:y|ies)|acceptable[ -]use|vpn|mfa|2fa|multi-?factor|two-?factor|"
    r"password|passphrase|software|install\w*|approv\w*|allowed|permitted|prohibited|compliance"
    r")\b",
    re.IGNORECASE,
)

RETRIEVE_NUDGE = (
    "Policy questions must be answered from the Knowledge Base. Call the retrieve tool "
    "with the user's question now, then answer from what it returns. If it returns "
    "nothing relevant, say the policy documents do not cover this before giving any "
    "general guidance, and offer to create a help desk ticket."
)

FALLBACK_MESSAGE = (
    "I couldn't retrieve the relevant IT policy documents, so I can't answer that "
    "reliably. I can create a help desk ticket so someone can follow up. Would you like "
    "me to?"
)


def is_policy_question(text: str) -> bool:
    return bool(POLICY_PATTERN.search(text))


def _last_user_text(messages) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            return " ".join(block["text"] for block in message.get("content", []) if "text" in block)
    return ""


class RequireRetrievalHook(HookProvider):
    """Reject policy answers that were not grounded in a `retrieve` call.

    State lives on the instance, which is safe because Strands raises
    ConcurrencyException for overlapping invocations on one agent.

    Known limits: only the new user message is inspected, so a follow-up that does not
    name a policy topic ("what about on my phone?") is left to the prompt instruction.
    A turn that called any other tool (e.g. CreateTicket) is not forced to retrieve, so
    a ticket request is never repeated.
    """

    def __init__(self, retrieve_tool_name: str = "retrieve", max_retries: int = 2):
        self.retrieve_tool_name = retrieve_tool_name
        self.max_retries = max_retries
        self._resume_pending = False
        self._new_turn("")

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeInvocationEvent, self._on_before_invocation)
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)
        registry.add_callback(AfterInvocationEvent, self._on_after_invocation)

    def _new_turn(self, question: str) -> None:
        self._question = question
        self._retrieved = False
        self._other_tool_called = False
        self._retries = 0

    def _on_before_invocation(self, event: BeforeInvocationEvent) -> None:
        if self._resume_pending:
            # Our own resume re-enters here: keep the state of the turn it belongs to.
            self._resume_pending = False
            return
        self._new_turn(_last_user_text(event.messages))

    def _on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        if event.tool_use["name"] != self.retrieve_tool_name:
            self._other_tool_called = True
        elif isinstance(event.result, dict) and event.result.get("status") == "success":
            self._retrieved = True

    def _on_after_invocation(self, event: AfterInvocationEvent) -> None:
        result = event.result
        if result is None or result.stop_reason != "end_turn":
            return
        if self._retrieved or self._other_tool_called or not is_policy_question(self._question):
            return

        if self._retries < self.max_retries:
            self._retries += 1
            self._resume_pending = True
            logger.warning(
                "Policy answer without retrieval, asking the agent to retrieve (attempt %d/%d)",
                self._retries,
                self.max_retries,
            )
            event.resume = RETRIEVE_NUDGE
            return

        logger.error("Policy answer without retrieval after %d retries, returning fallback", self._retries)
        result.message["content"] = [{"text": FALLBACK_MESSAGE}]
