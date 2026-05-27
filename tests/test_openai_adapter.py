"""OpenAI / NIM adapter tests (mocked HTTP — no live API)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from context_manager.errors import LLMAuthError, LLMTimeoutError
from context_manager.agent.llm_config import LLMConfig, NIM_DEFAULT_BASE_URL, NIM_DEFAULT_MODEL
from context_manager.agent.llm_factory import create_llm, llm_label
from context_manager.agent.openai_adapter import OpenAIChatAdapter, messages_to_openai
from context_manager.models import Message


def test_llm_config_nim_defaults():
    cfg = LLMConfig(provider="nim")
    with patch.dict("os.environ", {}, clear=True):
        assert cfg.resolved_base_url() == NIM_DEFAULT_BASE_URL
        assert cfg.resolved_model() == NIM_DEFAULT_MODEL


def test_llm_config_reads_nvidia_env_vars():
    env = {
        "NVIDIA_MODEL": "deepseek-ai/deepseek-v4-flash",
        "NVIDIA_NIM_API_BASE": "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY": "nvapi-test",
    }
    with patch.dict("os.environ", env, clear=True):
        cfg = LLMConfig.from_env(provider="nim")
        assert cfg.model == "deepseek-ai/deepseek-v4-flash"
        assert cfg.base_url == "https://integrate.api.nvidia.com/v1"
        assert cfg.resolved_api_key() == "nvapi-test"
        assert cfg.resolved_model() == "deepseek-ai/deepseek-v4-flash"
        assert cfg.resolved_base_url() == "https://integrate.api.nvidia.com/v1"


def test_messages_to_openai_includes_tool_calls_metadata():
    msgs = [
        Message(
            "assistant",
            "",
            metadata={
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_archived", "arguments": "{}"},
                    }
                ]
            },
        ),
        Message("tool", "segment list", tool_call_id="call_1", name="list_archived"),
    ]
    api = messages_to_openai(msgs)
    assert api[0]["role"] == "assistant"
    assert "tool_calls" in api[0]
    assert api[1]["tool_call_id"] == "call_1"


def test_create_llm_mock():
    llm = create_llm(LLMConfig(provider="mock"))
    from context_manager.agent.mock_llm import MockLLM

    assert isinstance(llm, MockLLM)


@patch("openai.OpenAI")
def test_openai_adapter_parses_tool_calls(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    fn = MagicMock()
    fn.name = "recall_segment"
    fn.arguments = '{"segment_id": "abc-123"}'

    tc = MagicMock()
    tc.id = "call_xyz"
    tc.function = fn

    choice_msg = MagicMock()
    choice_msg.content = "I will recall that segment."
    choice_msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = choice_msg

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 5

    response = MagicMock()
    response.choices = [choice]
    response.model = "test-model"
    response.usage = usage

    mock_client.chat.completions.create.return_value = response

    cfg = LLMConfig(provider="nim", api_key="test-key", model="meta/llama-test")
    adapter = OpenAIChatAdapter(cfg)
    result = adapter.complete([Message("user", "recall segment abc-123")], "recall segment abc-123")

    assert result.assistant_text == "I will recall that segment."
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "recall_segment"
    assert result.tool_calls[0].arguments["segment_id"] == "abc-123"
    assert result.tool_calls[0].id == "call_xyz"

    mock_openai_cls.assert_called_once_with(
        api_key="test-key",
        base_url=NIM_DEFAULT_BASE_URL,
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "meta/llama-test"
    assert call_kwargs["tools"] is not None


def test_openai_adapter_requires_api_key():
    cfg = LLMConfig(provider="openai", api_key=None)
    adapter = OpenAIChatAdapter(cfg)
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="Missing API key"):
            adapter.complete([], "hi")


@patch("openai.OpenAI")
def test_openai_adapter_maps_timeout_error(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    class APITimeoutError(Exception):
        pass

    mock_client.chat.completions.create.side_effect = APITimeoutError("timeout")
    adapter = OpenAIChatAdapter(LLMConfig(provider="nim", api_key="x"))
    with pytest.raises(LLMTimeoutError) as exc:
        adapter.complete([Message("user", "hello")], "hello")
    assert exc.value.envelope.normalized_code() == "E_LLM_TIMEOUT"


@patch("openai.OpenAI")
def test_openai_adapter_maps_auth_error(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    class AuthenticationError(Exception):
        pass

    mock_client.chat.completions.create.side_effect = AuthenticationError("bad key")
    adapter = OpenAIChatAdapter(LLMConfig(provider="openai", api_key="x"))
    with pytest.raises(LLMAuthError) as exc:
        adapter.complete([Message("user", "hello")], "hello")
    assert exc.value.envelope.normalized_code() == "E_LLM_AUTH"


def test_llm_label():
    assert "mock" in llm_label(LLMConfig(provider="mock"))
    assert "nim" in llm_label(LLMConfig(provider="nim", model="x"))
