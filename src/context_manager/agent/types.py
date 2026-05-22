from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, str]
    content: str = ""
    id: str | None = None


@dataclass
class LLMCompletion:
    """Model output for one completion call (may include tool calls)."""

    assistant_text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_model: str | None = None
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None


# Backward compatibility
MockLLMResponse = LLMCompletion
