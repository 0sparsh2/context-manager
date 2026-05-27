from __future__ import annotations

import json
from typing import Any, Protocol

from context_manager.errors import (
    ErrorCode,
    ErrorEnvelope,
    LLMAuthError,
    LLMProviderError,
    LLMTimeoutError,
)
from context_manager.agent.llm_config import LLMConfig
from context_manager.agent.tools_schema import TOOL_SCHEMAS
from context_manager.agent.types import LLMCompletion, ToolCall
from context_manager.models import Message

try:
    from openai import OpenAI as _OpenAI
except ImportError:  # pragma: no cover - exercised via adapter/tests without llm extra
    _OpenAI = None


class LLMClient(Protocol):
    def complete(self, hot_messages: list[Message], user_text: str) -> LLMCompletion: ...


def messages_to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "assistant" and m.metadata.get("tool_calls"):
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": m.metadata["tool_calls"],
                }
            )
            continue
        msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.name and m.role == "tool":
            msg["name"] = m.name
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        out.append(msg)
    return out


class OpenAIChatAdapter:
    """
    OpenAI Chat Completions API — also works with **NVIDIA NIM** via base_url.

    NIM: provider=`nim`, base_url=https://integrate.api.nvidia.com/v1, api_key=NVIDIA_API_KEY.
    Docs: https://docs.api.nvidia.com/nim/reference/llm-apis
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        api_key = self.config.resolved_api_key()
        if not api_key:
            raise ValueError(
                f"Missing API key for provider={self.config.provider!r}. "
                "Set NVIDIA_API_KEY (nim) or OPENAI_API_KEY (openai)."
            )
        if _OpenAI is None:
            raise ImportError(
                "Install the OpenAI SDK: pip install 'context-manager[llm]' or pip install openai"
            )

        kwargs: dict[str, Any] = {"api_key": api_key}
        base_url = self.config.resolved_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        self._client = _OpenAI(**kwargs)
        return self._client

    def complete(self, hot_messages: list[Message], user_text: str) -> LLMCompletion:
        client = self._get_client()
        api_messages = messages_to_openai(hot_messages)

        try:
            response = client.chat.completions.create(
                model=self.config.resolved_model(),
                messages=api_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout_seconds,
            )
        except Exception as exc:
            name = exc.__class__.__name__
            if name in {"APITimeoutError", "ReadTimeout"}:
                raise LLMTimeoutError(
                    ErrorEnvelope(
                        code=ErrorCode.LLM_TIMEOUT,
                        message=f"LLM request timed out for provider={self.config.provider}",
                        component="openai_adapter",
                        retryable=True,
                        boundary="provider_adapter",
                    )
                ) from exc
            if name in {"AuthenticationError", "PermissionDeniedError"}:
                raise LLMAuthError(
                    ErrorEnvelope(
                        code=ErrorCode.LLM_AUTH,
                        message="LLM authentication failed. Check API key and permissions.",
                        component="openai_adapter",
                        retryable=False,
                        boundary="provider_adapter",
                    )
                ) from exc
            raise LLMProviderError(
                ErrorEnvelope(
                    code=ErrorCode.LLM_PROVIDER,
                    message=f"LLM provider request failed: {name}",
                    component="openai_adapter",
                    retryable=False,
                    boundary="provider_adapter",
                )
            ) from exc

        choice = response.choices[0]
        msg = choice.message
        assistant_text = msg.content or ""

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                args: dict[str, str] = {}
                if fn.arguments:
                    try:
                        parsed = json.loads(fn.arguments)
                        args = {k: str(v) for k, v in parsed.items()}
                    except json.JSONDecodeError:
                        args = {"raw": fn.arguments}
                tool_calls.append(
                    ToolCall(
                        name=fn.name,
                        arguments=args,
                        id=tc.id,
                    )
                )

        usage = response.usage
        return LLMCompletion(
            assistant_text=assistant_text,
            tool_calls=tool_calls,
            raw_model=response.model,
            usage_prompt_tokens=usage.prompt_tokens if usage else None,
            usage_completion_tokens=usage.completion_tokens if usage else None,
        )
