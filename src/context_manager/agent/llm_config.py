from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Provider = Literal["mock", "openai", "nim"]

NIM_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"


def load_dotenv_if_present() -> bool:
    """
    Load project `.env` into os.environ (does not override existing vars).

    Looks for `.env` in the current working directory, then the package root.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        load_dotenv(cwd_env, override=False)
        return True

    # repo root: .../src/context_manager/agent/llm_config.py -> 4 parents up
    root_env = Path(__file__).resolve().parents[3] / ".env"
    if root_env.is_file():
        load_dotenv(root_env, override=False)
        return True
    return False


@dataclass
class LLMConfig:
    """
    LLM connection settings.

    **NVIDIA NIM** uses the OpenAI Python SDK with a custom base URL.
    Env vars (also loaded from `.env` via CLI):

    - `NVIDIA_API_KEY` or `NGC_API_KEY`
    - `NVIDIA_MODEL` (e.g. `deepseek-ai/deepseek-v4-flash`)
    - `NVIDIA_NIM_API_BASE` (default: https://integrate.api.nvidia.com/v1)
    """

    provider: Provider = "mock"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.2
    max_tokens: int = 1024
    max_tool_rounds: int = 5
    timeout_seconds: float = 300.0

    @classmethod
    def from_env(cls, provider: Provider | None = None) -> LLMConfig:
        load_dotenv_if_present()
        prov = (provider or os.environ.get("CONTEXT_MANAGER_LLM_PROVIDER", "mock")).lower()
        if prov not in ("mock", "openai", "nim"):
            prov = "mock"

        model = os.environ.get("CONTEXT_MANAGER_MODEL")
        base_url = os.environ.get("CONTEXT_MANAGER_BASE_URL")
        api_key = os.environ.get("CONTEXT_MANAGER_API_KEY")

        if prov == "nim":
            model = model or os.environ.get("NVIDIA_MODEL")
            base_url = base_url or os.environ.get("NVIDIA_NIM_API_BASE")

        return cls(
            provider=prov,  # type: ignore[arg-type]
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=float(os.environ.get("CONTEXT_MANAGER_TEMPERATURE", "0.2")),
            max_tokens=int(os.environ.get("CONTEXT_MANAGER_MAX_TOKENS", "1024")),
            timeout_seconds=float(
                os.environ.get(
                    "CONTEXT_MANAGER_TIMEOUT",
                    os.environ.get("NVIDIA_NIM_TIMEOUT", "300"),
                )
            ),
        )

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        if self.provider == "nim":
            return os.environ.get("NVIDIA_MODEL") or NIM_DEFAULT_MODEL
        if self.provider == "openai":
            return OPENAI_DEFAULT_MODEL
        return "mock"

    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.provider == "nim":
            return os.environ.get("NVIDIA_API_KEY") or os.environ.get("NGC_API_KEY")
        if self.provider == "openai":
            return os.environ.get("OPENAI_API_KEY")
        return None

    def resolved_base_url(self) -> str | None:
        if self.base_url:
            return self.base_url
        if self.provider == "nim":
            return (
                os.environ.get("NVIDIA_NIM_API_BASE")
                or os.environ.get("NVIDIA_BASE_URL")
                or NIM_DEFAULT_BASE_URL
            )
        return None  # OpenAI default
