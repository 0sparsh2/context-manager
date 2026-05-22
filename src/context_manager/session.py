from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from context_manager.models import Message, TrimMode
from context_manager.policies.tools import ToolResultPolicy
from context_manager.policies.trim import HeadTailTrimPolicy, LastNTrimPolicy, apply_trim
from context_manager.store.sqlite import SQLiteSegmentStore


@dataclass
class ContextConfig:
    trim_mode: TrimMode = TrimMode.HEAD_TAIL
    keep_last_n: int = 12
    head_messages: int = 1
    tail_messages: int = 6
    preview_chars: int = 80
    tool_policy_enabled: bool = True
    db_path: str | None = None


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
    messages: list[Message] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self._store is None:
            self._store = SQLiteSegmentStore(self.config.db_path)

    @property
    def store(self) -> SQLiteSegmentStore:
        assert self._store is not None
        return self._store

    @classmethod
    def create(cls, config: ContextConfig | None = None) -> ContextSession:
        return cls(session_id=str(uuid.uuid4()), config=config or ContextConfig())

    def append(self, message: Message) -> None:
        self.messages.append(message)

    def append_many(self, messages: list[Message]) -> None:
        self.messages.extend(messages)

    def total_chars(self) -> int:
        return sum(m.char_count() for m in self.messages)

    def hot_char_count(self) -> int:
        return sum(m.char_count() for m in self.get_hot_context())

    def get_hot_context(self) -> list[Message]:
        """Apply tool policy then trim policy; system messages preserved."""
        msgs = [Message(**{**m.to_dict(), "metadata": dict(m.metadata)}) for m in self.messages]
        if self.config.tool_policy_enabled:
            tool_policy = ToolResultPolicy(enabled=True)
            msgs = tool_policy.apply(
                msgs,
                session_id=self.session_id,
                position_offset=0,
                save_segment=self.store.save,
                preview_chars=self.config.preview_chars,
            )

        if self.config.trim_mode == TrimMode.LAST_N:
            policy = LastNTrimPolicy(keep_last=self.config.keep_last_n)
        else:
            policy = HeadTailTrimPolicy(
                head_messages=self.config.head_messages,
                tail_messages=self.config.tail_messages,
            )

        return apply_trim(
            policy,
            msgs,
            session_id=self.session_id,
            position_offset=0,
            save_segment=self.store.save,
            preview_chars=self.config.preview_chars,
        )

    def recall(self, segment_id: str) -> str | None:
        seg = self.store.get(segment_id)
        return seg.content if seg else None

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
