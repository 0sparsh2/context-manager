from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from context_manager.models import Message, TrimMode


@dataclass
class ProviderCapabilities:
    provider: str
    supports_server_compaction: bool = False
    supports_prompt_cache: bool = False
    max_input_tokens: int = 128_000
    preferred_trim_mode: TrimMode = TrimMode.LAST_N


@dataclass
class CompactionDecision:
    trim_mode: TrimMode
    reason: str
    strategy: str
    confidence: float = 1.0


class CompactionStrategy(Protocol):
    def choose(self, *, capabilities: ProviderCapabilities, message_count: int) -> CompactionDecision: ...


class CapabilityAwareCompactionStrategy:
    """
    Provider-aware strategy that keeps behavior deterministic by default.
    """

    def choose(self, *, capabilities: ProviderCapabilities, message_count: int) -> CompactionDecision:
        safe_count = max(0, message_count)
        if safe_count <= 2:
            return CompactionDecision(
                trim_mode=capabilities.preferred_trim_mode,
                reason="short conversation; follow provider default trim mode",
                strategy="capability_aware_v2",
                confidence=1.0,
            )
        if capabilities.supports_server_compaction and message_count > 16:
            return CompactionDecision(
                trim_mode=TrimMode.HEAD_TAIL,
                reason="provider supports server compaction; keep stable anchor/tail locally",
                strategy="capability_aware_v2",
                confidence=0.9,
            )
        if capabilities.max_input_tokens < 64_000 and safe_count > 8:
            return CompactionDecision(
                trim_mode=TrimMode.HEAD_TAIL,
                reason="smaller context model; prefer aggressive archival of middle",
                strategy="capability_aware_v2",
                confidence=0.8,
            )
        return CompactionDecision(
            trim_mode=capabilities.preferred_trim_mode,
            reason="large context model; keep deterministic conversational recency",
            strategy="capability_aware_v2",
            confidence=0.7,
        )


def capabilities_for_provider(provider: str) -> ProviderCapabilities:
    normalized = provider.lower().strip()
    if normalized == "openai":
        return ProviderCapabilities(
            provider=normalized,
            supports_server_compaction=False,
            supports_prompt_cache=True,
            max_input_tokens=128_000,
            preferred_trim_mode=TrimMode.LAST_N,
        )
    if normalized == "nim":
        return ProviderCapabilities(
            provider=normalized,
            supports_server_compaction=False,
            supports_prompt_cache=False,
            max_input_tokens=32_000,
            preferred_trim_mode=TrimMode.HEAD_TAIL,
        )
    if normalized == "anthropic":
        return ProviderCapabilities(
            provider=normalized,
            supports_server_compaction=True,
            supports_prompt_cache=True,
            max_input_tokens=200_000,
            preferred_trim_mode=TrimMode.HEAD_TAIL,
        )
    return ProviderCapabilities(
        provider=normalized or "unknown",
        max_input_tokens=32_000,
        preferred_trim_mode=TrimMode.HEAD_TAIL,
    )


def summarize_compaction_trace(
    *,
    decision: CompactionDecision,
    capabilities: ProviderCapabilities,
    full_messages: int,
    hot_messages: list[Message],
) -> dict[str, object]:
    return {
        "strategy": decision.strategy,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "trim_mode": decision.trim_mode.value,
        "provider": capabilities.provider,
        "provider_caps": {
            "supports_server_compaction": capabilities.supports_server_compaction,
            "supports_prompt_cache": capabilities.supports_prompt_cache,
            "max_input_tokens": capabilities.max_input_tokens,
            "preferred_trim_mode": capabilities.preferred_trim_mode.value,
        },
        "full_messages": full_messages,
        "hot_messages": len(hot_messages),
    }
