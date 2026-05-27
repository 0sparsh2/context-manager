from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TrimMode(str, Enum):
    LAST_N = "last_n"
    HEAD_TAIL = "head_tail"


@dataclass
class Message:
    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def char_count(self) -> int:
        return len(self.content)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name is not None:
            out["name"] = self.name
        if self.tool_call_id is not None:
            out["tool_call_id"] = self.tool_call_id
        if self.metadata:
            out["metadata"] = self.metadata
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            metadata=data.get("metadata") or {},
        )


@dataclass
class Segment:
    """Archived message chunk addressable outside the hot context window."""

    id: str
    session_id: str
    position: int
    role: str
    preview: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    created_at_unix: float = 0.0
    verified_at_unix: float = 0.0
    source: str = "session"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "position": self.position,
            "role": self.role,
            "preview": self.preview,
            "content": self.content,
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "created_at_unix": self.created_at_unix,
            "verified_at_unix": self.verified_at_unix,
            "source": self.source,
        }
