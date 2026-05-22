from __future__ import annotations

from context_manager.agent.llm_config import LLMConfig, Provider
from context_manager.agent.mock_llm import MockLLM
from context_manager.agent.openai_adapter import LLMClient, OpenAIChatAdapter


def create_llm(config: LLMConfig | None = None) -> LLMClient:
    cfg = config or LLMConfig(provider="mock")
    if cfg.provider == "mock":
        return MockLLM()
    if cfg.provider in ("openai", "nim"):
        return OpenAIChatAdapter(cfg)
    raise ValueError(f"Unknown LLM provider: {cfg.provider!r}")


def llm_label(config: LLMConfig) -> str:
    if config.provider == "mock":
        return "mock"
    model = config.resolved_model()
    base = config.resolved_base_url() or "https://api.openai.com/v1"
    return f"{config.provider} model={model} base_url={base}"
