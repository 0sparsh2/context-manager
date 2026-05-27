from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from context_manager.memory.backends import MemoryBackend, create_memory_backend
from context_manager.models import Message, TrimMode
from context_manager.policies.compaction import (
    CapabilityAwareCompactionStrategy,
    CompactionStrategy,
    capabilities_for_provider,
    summarize_compaction_trace,
)
from context_manager.policies.tools import ToolResultPolicy
from context_manager.policies.trim import HeadTailTrimPolicy, LastNTrimPolicy, apply_trim
from context_manager.store.sqlite import SQLiteSegmentStore


@dataclass
class ContextConfig:
    trim_mode: TrimMode = TrimMode.HEAD_TAIL
    provider_name: str = "mock"
    keep_last_n: int = 12
    head_messages: int = 1
    tail_messages: int = 6
    preview_chars: int = 80
    tool_policy_enabled: bool = True
    db_path: str | None = None
    recall_scan_limit: int = 5000
    recall_require_verified: bool = False
    recall_max_age_seconds: int = 60 * 60 * 24 * 14
    metrics_hook: Callable[[str, dict[str, Any]], None] | None = None


@dataclass
class ContextSession:
    """
    Orchestrates full transcript storage, policy application, and segment recall.

    - `messages`: full history (never mutated on append)
    - `get_hot_context()`: system + trim + tool policies applied
    - `recall(segment_id)`: fetch archived middle/tool content from warm store
    """

    session_id: str
    config: ContextConfig = field(default_factory=ContextConfig)
    _store: SQLiteSegmentStore | None = field(default=None, repr=False)
    _memory_backend: MemoryBackend | None = field(default=None, repr=False)
    _compaction_strategy: CompactionStrategy | None = field(default=None, repr=False)
    messages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self._store is None:
            self._store = SQLiteSegmentStore(self.config.db_path)
        if self._memory_backend is None:
            self._memory_backend = create_memory_backend()
        if self._compaction_strategy is None:
            self._compaction_strategy = CapabilityAwareCompactionStrategy()

    @property
    def store(self) -> SQLiteSegmentStore:
        assert self._store is not None
        return self._store

    @property
    def memory_backend(self) -> MemoryBackend:
        assert self._memory_backend is not None
        return self._memory_backend

    @classmethod
    def create(cls, config: ContextConfig | None = None) -> ContextSession:
        return cls(session_id=str(uuid.uuid4()), config=config or ContextConfig())

    def append(self, message: Message) -> None:
        self.messages.append(message)
        # Best-effort cross-session fact memory; only for user/system facts.
        if message.role in {"user", "system"} and ":" in message.content and self.memory_backend.enabled():
            key, value = message.content.split(":", 1)
            self.memory_backend.write_fact(
                session_id=self.session_id,
                key=key.strip()[:120],
                value=value.strip()[:2000],
                source=message.role,
            )

    def append_many(self, messages: list[Message]) -> None:
        self.messages.extend(messages)

    def total_chars(self) -> int:
        return sum(m.char_count() for m in self.messages)

    def hot_char_count(self) -> int:
        return sum(m.char_count() for m in self.get_hot_context())

    def _emit_metric(self, name: str, **fields: Any) -> None:
        hook = self.config.metrics_hook
        if hook is None:
            return
        try:
            hook(name, fields)
        except Exception:
            # Metrics must never break core behavior.
            return

    def get_hot_context(self) -> list[Message]:
        """Apply tool policy then trim policy; system messages preserved."""
        full_chars = self.total_chars()
        msgs = [Message(**{**m.to_dict(), "metadata": dict(m.metadata)}) for m in self.messages]
        capabilities = capabilities_for_provider(self.config.provider_name)
        decision = self._compaction_strategy.choose(
            capabilities=capabilities,
            message_count=len(msgs),
        )
        if self.config.tool_policy_enabled:
            tool_policy = ToolResultPolicy(enabled=True)
            msgs = tool_policy.apply(
                msgs,
                session_id=self.session_id,
                position_offset=0,
                save_segment=self.store.save,
                preview_chars=self.config.preview_chars,
            )

        selected_mode = self.config.trim_mode
        if self.config.trim_mode == TrimMode.HEAD_TAIL and len(msgs) >= 6:
            # allow strategy override while keeping current default behavior for small chats
            selected_mode = decision.trim_mode
        if selected_mode == TrimMode.LAST_N:
            policy = LastNTrimPolicy(keep_last=self.config.keep_last_n)
        else:
            policy = HeadTailTrimPolicy(
                head_messages=self.config.head_messages,
                tail_messages=self.config.tail_messages,
            )

        hot = apply_trim(
            policy,
            msgs,
            session_id=self.session_id,
            position_offset=0,
            save_segment=self.store.save,
            preview_chars=self.config.preview_chars,
        )
        self._emit_metric(
            "context.trim_applied",
            hot_chars=sum(m.char_count() for m in hot),
            full_chars=full_chars,
            archive_count=len(self.list_archived_segments()),
            compaction_strategy=decision.strategy,
            compaction_reason=decision.reason,
            trim_mode=selected_mode.value,
            provider=self.config.provider_name,
            memory_backend_enabled=self.memory_backend.enabled(),
        )
        self._emit_metric(
            "context.compaction_trace",
            **summarize_compaction_trace(
                decision=decision,
                capabilities=capabilities,
                full_messages=len(self.messages),
                hot_messages=hot,
            ),
        )
        return hot

    def recall(self, segment_id: str) -> str | None:
        started = time.perf_counter()
        seg = self.store.get(segment_id)
        hit = seg is not None
        verification_status = "not_found"
        freshness_age_seconds = -1
        gated = False
        content: str | None = None
        if seg is not None:
            now = time.time()
            age_seconds = max(0, int(now - seg.created_at_unix))
            freshness_age_seconds = age_seconds
            is_fresh = age_seconds <= self.config.recall_max_age_seconds
            verified = bool(seg.verified_at_unix and seg.verified_at_unix > 0)
            verification_status = "verified" if verified else "unverified"
            if self.config.recall_require_verified and not verified:
                gated = True
            elif not is_fresh:
                gated = True
                verification_status = "stale"
            else:
                content = seg.content
        self._emit_metric(
            "context.recall_attempt",
            segment_id=segment_id,
            hit=hit,
            verification_status=verification_status,
            freshness_age_seconds=freshness_age_seconds,
            policy_require_verified=self.config.recall_require_verified,
            policy_max_age_seconds=self.config.recall_max_age_seconds,
            gated=gated,
            recall_latency_ms=(time.perf_counter() - started) * 1000.0,
        )
        return content

    def recall_diagnostics(self, segment_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        seg = self.store.get(segment_id)
        if seg is None:
            return {"segment_id": segment_id, "hit": False, "allowed": False}
        now = time.time()
        age_seconds = max(0, int(now - seg.created_at_unix))
        verified = bool(seg.verified_at_unix and seg.verified_at_unix > 0)
        is_fresh = age_seconds <= self.config.recall_max_age_seconds
        allowed = True
        reason = "ok"
        if self.config.recall_require_verified and not verified:
            allowed = False
            reason = "unverified"
        elif not is_fresh:
            allowed = False
            reason = "stale"
        return {
            "segment_id": segment_id,
            "hit": True,
            "allowed": allowed,
            "reason": reason,
            "age_seconds": age_seconds,
            "verified": verified,
            "latency_ms": (time.perf_counter() - started) * 1000.0,
        }

    def compaction_diagnostics(self) -> dict[str, Any]:
        caps = capabilities_for_provider(self.config.provider_name)
        decision = self._compaction_strategy.choose(capabilities=caps, message_count=len(self.messages))
        hot = self.get_hot_context()
        return summarize_compaction_trace(
            decision=decision,
            capabilities=caps,
            full_messages=len(self.messages),
            hot_messages=hot,
        )

    def list_archived_segments(self) -> list:
        return self.store.list_session(self.session_id)

    def segment_ids_in_hot_context(self) -> list[str]:
        ids: list[str] = []
        for msg in self.get_hot_context():
            sid = msg.metadata.get("segment_id")
            if sid:
                ids.append(str(sid))
        return ids

    def close(self) -> None:
        self.store.close()
