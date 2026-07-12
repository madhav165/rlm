"""Tests for recursive RLM calls from DockerREPL."""

import threading
from unittest.mock import MagicMock, patch

import rlm.core.rlm as rlm_module
from rlm import RLM
from rlm.core.types import RLMChatCompletion, UsageSummary
from rlm.environments.docker_repl import LLMProxyHandler, _build_exec_script


def make_completion(response: str) -> RLMChatCompletion:
    return RLMChatCompletion(
        root_model="test-model",
        prompt="test",
        response=response,
        usage_summary=UsageSummary(model_usage_summaries={}),
        execution_time=0.1,
    )


def make_handler(subcall_fn):
    handler = object.__new__(LLMProxyHandler)
    handler.subcall_fn = subcall_fn
    handler.pending_calls = []
    handler.lock = threading.Lock()
    return handler


def test_exec_script_exposes_recursive_helpers():
    script = _build_exec_script("result = rlm_query('test')", 1234)

    assert "def rlm_query(prompt, model=None):" in script
    assert "def rlm_query_batched(prompts, model=None):" in script
    assert 'requests.post(f"{PROXY}/rlm_query"' in script
    assert 'requests.post(f"{PROXY}/rlm_query_batched"' in script
    assert '"rlm_query": rlm_query' in script
    assert '"rlm_query_batched": rlm_query_batched' in script


def test_recursive_handler_uses_subcall_callback_and_tracks_completion():
    completion = make_completion("child response")
    subcall_fn = MagicMock(return_value=completion)
    handler = make_handler(subcall_fn)

    result = handler._handle_recursive({"prompt": "inspect repo", "model": "child-model"})

    assert result == {"response": "child response"}
    assert handler.pending_calls == [completion]
    subcall_fn.assert_called_once_with("inspect repo", "child-model")


def test_recursive_batched_handler_isolates_call_errors():
    subcall_fn = MagicMock(
        side_effect=[make_completion("first"), RuntimeError("failed"), make_completion("third")]
    )
    handler = make_handler(subcall_fn)

    result = handler._handle_recursive_batched({"prompts": ["one", "two", "three"], "model": None})

    assert result == {"responses": ["first", "Error: RLM query failed - failed", "third"]}
    assert [completion.response for completion in handler.pending_calls] == ["first", "third"]


def test_recursive_child_inherits_mcp_servers():
    captured_kwargs = {}

    class ChildRLM:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def completion(self, prompt, root_prompt=None):
            return make_completion("child response")

        def close(self):
            pass

    parent = RLM(max_depth=3)
    parent.mcp_servers = {"memory": {"command": "memory-server", "type": "stdio"}}

    with patch.object(rlm_module, "RLM", ChildRLM):
        result = parent._subcall("inspect repo")

    assert result.response == "child response"
    assert captured_kwargs["mcp_servers"] == parent.mcp_servers
