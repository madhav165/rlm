"""Tests for the final-answer fallback after the iteration limit."""

from unittest.mock import MagicMock

from rlm import RLM


def test_default_answer_starts_a_user_turn_after_assistant_response():
    rlm = RLM()
    lm_handler = MagicMock()
    lm_handler.completion.return_value = "final response"
    message_history = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": "unfinished response"},
    ]

    result = rlm._default_answer(message_history, lm_handler)

    assert result == "final response"
    prompt = lm_handler.completion.call_args.args[0]
    assert [message["role"] for message in prompt[-2:]] == ["assistant", "user"]
    assert message_history[-1] == {"role": "assistant", "content": "unfinished response"}
