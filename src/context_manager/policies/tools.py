from __future__ import annotations

from dataclasses import dataclass

from context_manager.models import Message
from context_manager.policies.trim import _stored_placeholder


@dataclass
class ToolResultPolicy:
    """Keep only the latest tool result per tool name in hot context; archive older ones."""

    enabled: bool = True

    def apply(
        self,
        messages: list[Message],
        *,
        session_id: str,
        position_offset: int,
        save_segment,
        preview_chars: int,
    ) -> list[Message]:
        if not self.enabled:
            return list(messages)

        latest_index: dict[str, int] = {}
        for i, msg in enumerate(messages):
            if msg.role == "tool" and msg.name:
                latest_index[msg.name] = i

        if not latest_index:
            return list(messages)

        out: list[Message] = []
        pos = position_offset
        for i, msg in enumerate(messages):
            if msg.role == "tool" and msg.name and latest_index.get(msg.name) != i:
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
            else:
                out.append(msg)
            pos += 1
        return out
