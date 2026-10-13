from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from strands.hooks import AfterInvocationEvent, AfterToolCallEvent, BeforeInvocationEvent

from askit_hooks import FALLBACK_MESSAGE, RETRIEVE_NUDGE, RequireRetrievalHook, is_policy_question

POLICY_QUESTION = "Am I allowed to use a personal laptop on the VPN?"


def user_message(text):
    return [{"role": "user", "content": [{"text": text}]}]


def before(hook, text):
    hook._on_before_invocation(BeforeInvocationEvent(agent=Mock(), messages=user_message(text)))


def tool_call(hook, name, status="success"):
    hook._on_after_tool_call(
        AfterToolCallEvent(
            agent=Mock(),
            selected_tool=None,
            tool_use={"name": name, "toolUseId": "t1", "input": {}},
            invocation_state={},
            result={"toolUseId": "t1", "status": status, "content": []},
        )
    )


def after(hook, stop_reason="end_turn"):
    result = SimpleNamespace(stop_reason=stop_reason, message={"role": "assistant", "content": [{"text": "answer"}]})
    event = AfterInvocationEvent(agent=Mock(), result=result)
    hook._on_after_invocation(event)
    return event


@pytest.mark.parametrize(
    "text",
    [
        POLICY_QUESTION,
        "What is the password policy?",
        "How do I set up MFA?",
        "Is Slack an approved application?",
        "Can I install Zoom on my work laptop?",
        "What does the acceptable use policy say about personal email?",
    ],
)
def test_policy_questions_are_detected(text):
    assert is_policy_question(text)


@pytest.mark.parametrize("text", ["Hello!", "My monitor is flickering", "What is the status of ticket INC-1042?"])
def test_non_policy_questions_are_not_detected(text):
    assert not is_policy_question(text)


def test_policy_answer_without_retrieval_is_resumed_with_nudge():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)

    event = after(hook)

    assert event.resume == RETRIEVE_NUDGE


def test_policy_answer_after_successful_retrieval_is_left_alone():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)
    tool_call(hook, "retrieve")

    event = after(hook)

    assert event.resume is None
    assert event.result.message["content"] == [{"text": "answer"}]


def test_failed_retrieval_does_not_count():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)
    tool_call(hook, "retrieve", status="error")

    assert after(hook).resume == RETRIEVE_NUDGE


def test_non_policy_question_is_left_alone():
    hook = RequireRetrievalHook()
    before(hook, "My monitor is flickering")

    assert after(hook).resume is None


def test_ticket_turn_is_not_forced_to_retrieve():
    hook = RequireRetrievalHook()
    before(hook, "My VPN is down and I cannot work, please open a ticket")
    tool_call(hook, "askit-target___CreateTicket")

    assert after(hook).resume is None


def test_non_end_turn_stop_reason_is_ignored():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)

    assert after(hook, stop_reason="max_tokens").resume is None


def test_retries_are_bounded_then_fallback_replaces_the_answer():
    hook = RequireRetrievalHook(max_retries=2)
    before(hook, POLICY_QUESTION)

    first = after(hook)
    assert first.resume == RETRIEVE_NUDGE
    before(hook, RETRIEVE_NUDGE)  # the resume re-enters the invocation

    second = after(hook)
    assert second.resume == RETRIEVE_NUDGE
    before(hook, RETRIEVE_NUDGE)

    third = after(hook)
    assert third.resume is None
    assert third.result.message["content"] == [{"text": FALLBACK_MESSAGE}]


def test_retrieval_on_the_resumed_pass_ends_the_loop():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)
    assert after(hook).resume == RETRIEVE_NUDGE

    before(hook, RETRIEVE_NUDGE)
    tool_call(hook, "retrieve")
    final = after(hook)

    assert final.resume is None
    assert final.result.message["content"] == [{"text": "answer"}]


def test_state_resets_on_a_new_user_turn():
    hook = RequireRetrievalHook()
    before(hook, POLICY_QUESTION)
    tool_call(hook, "retrieve")
    after(hook)

    before(hook, "What is the password policy?")

    assert after(hook).resume == RETRIEVE_NUDGE
