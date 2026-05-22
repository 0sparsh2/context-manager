from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from context_manager.models import Message


class SegmentSaver(Protocol):
    def save(
        self,
        *,
        session_id: str,
        position: int,
        role: str,
        content: str,
        preview_chars: int = 80,
        name: str | None = None,
        tool_call_id: str | None = None,
    ): ...


STORED_PREFIX = "[archived segment"


def _stored_placeholder(segment_id: str, preview: str) -> str:
    return f"{STORED_PREFIX} id={segment_id}] {preview}"


def _is_system(msg: Message) -> bool:
    return msg.role == "system"


@dataclass
class LastNTrimPolicy:
    """Keep system messages and the last N non-system messages."""

    keep_last: int = 12
    always_keep_system: bool = True

    def apply(
        self,
        messages: list[Message],
        *,
        session_id: str,
        position_offset: int,
        save_segment: Callable[..., object],
        preview_chars: int,
    ) -> list[Message]:
        system = [m for m in messages if _is_system(m)] if self.always_keep_system else []
        non_system = [m for m in messages if not _is_system(m)]
        if len(non_system) <= self.keep_last:
            return list(messages)

        archived = non_system[: len(non_system) - self.keep_last]
        kept_tail = non_system[len(non_system) - self.keep_last :]
        out: list[Message] = []
        pos = position_offset
        for msg in archived:
            if msg.metadata.get("archived"):
                out.append(msg)
                pos += 1
                continue
            seg = save_segment(
                session_id=session_id,
                position=pos,
                role=msg.role,
                content=msg.content,
                preview_chars=preview_chars,
                name=msg.name,
                tool_call_id=msg.tool_call_id,
            )
            out.append(
                Message(
                    role=msg.role,
                    content=_stored_placeholder(seg.id, seg.preview),
                    name=msg.name,
                    tool_call_id=msg.tool_call_id,
                    metadata={**msg.metadata, "segment_id": seg.id, "archived": True},
                )
            )
            pos += 1
        return system + out + kept_tail


@dataclass
class HeadTailTrimPolicy:
    """Keep first N and last M non-system messages; archive the middle (Alex-style)."""

    head_messages: int = 1
    tail_messages: int = 6
    always_keep_system: bool = True

    def apply(
        self,
        messages: list[Message],
        *,
        session_id: str,
        position_offset: int,
        save_segment: Callable[..., object],
        preview_chars: int,
    ) -> list[Message]:
        system = [m for m in messages if _is_system(m)] if self.always_keep_system else []
        non_system = [m for m in messages if not _is_system(m)]
        if len(non_system) <= self.head_messages + self.tail_messages:
            return list(messages)

        head = non_system[: self.head_messages]
        tail = non_system[-self.tail_messages :]
        middle = non_system[self.head_messages : len(non_system) - self.tail_messages]

        archived_out: list[Message] = []
        pos = position_offset
        for msg in middle:
            if msg.metadata.get("archived"):
                archived_out.append(msg)
                pos += 1
                continue
            seg = save_segment(
                session_id=session_id,
                position=pos,
                role=msg.role,
                content=msg.content,
                preview_chars=preview_chars,
                name=msg.name,
                tool_call_id=msg.tool_call_id,
            )
            archived_out.append(
                Message(
                    role=msg.role,
                    content=_stored_placeholder(seg.id, seg.preview),
                    name=msg.name,
                    tool_call_id=msg.tool_call_id,
                    metadata={**msg.metadata, "segment_id": seg.id, "archived": True},
                )
            )
            pos += 1

        return system + head + archived_out + tail


def apply_trim(
    policy: LastNTrimPolicy | HeadTailTrimPolicy,
    messages: list[Message],
    *,
    session_id: str,
    position_offset: int,
    save_segment: Callable[..., object],
    preview_chars: int = 80,
) -> list[Message]:
    return policy.apply(
        messages,
        session_id=session_id,
        position_offset=position_offset,
        save_segment=save_segment,
        preview_chars=preview_chars,
    )
