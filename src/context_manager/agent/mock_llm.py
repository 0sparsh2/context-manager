from __future__ import annotations

import re

from context_manager.agent.types import LLMCompletion, ToolCall
from context_manager.models import Message


class MockLLM:
    """
    Deterministic stand-in for an LLM.

    Reads only `hot_messages` (what a real API would receive) and returns
    assistant text plus optional tool calls. Business logic is keyword-driven
    so demos and tests are stable.
    """

    def complete(self, hot_messages: list[Message], user_text: str) -> LLMCompletion:
        hot_text = "\n".join(f"{m.role}: {m.content}" for m in hot_messages)
        lower = user_text.lower()

        if m := re.search(r"segment[_\s-]?id[=:\s]+([a-f0-9-]{8,})", lower):
            seg_id = m.group(1)
            return LLMCompletion(
                assistant_text=f"I will recall segment {seg_id}.",
                tool_calls=[
                    ToolCall(
                        name="recall_segment",
                        arguments={"segment_id": seg_id},
                    )
                ],
            )

        if "list archived" in lower or "list segments" in lower:
            return LLMCompletion(
                assistant_text="Listing archived segments.",
                tool_calls=[ToolCall(name="list_archived", arguments={})],
            )

        if ("search" in lower or "trace" in lower or "spans" in lower) and not lower.startswith(
            ("what was", "what is", "list archived")
        ):
            query = user_text.strip()
            return LLMCompletion(
                assistant_text="Searching observability backend for matching spans.",
                tool_calls=[
                    ToolCall(
                        name="search_spans",
                        arguments={"query": query},
                        content=self._span_blob("auth-gateway", "RUN_A"),
                    ),
                    ToolCall(
                        name="search_spans",
                        arguments={"query": query},
                        content=self._span_blob("payment-service", "RUN_B"),
                    ),
                    ToolCall(
                        name="search_spans",
                        arguments={"query": query},
                        content=self._span_blob(
                            "payment-service",
                            "RUN_LATEST",
                            extra=" status=500 error=CardDeclined",
                        ),
                    ),
                ],
            )

        if "read file" in lower or "read_file" in lower:
            path = "src/context_manager/session.py"
            if "path=" in lower:
                path = re.sub(r".*path=\s*(\S+).*", r"\1", user_text, flags=re.I) or path
            return LLMCompletion(
                assistant_text=f"Reading {path}.",
                tool_calls=[
                    ToolCall(
                        name="read_file",
                        arguments={"path": path},
                        content=f"FILE:{path}\nKEY_FINDING: duplicate archive when policies stack\n"
                        + ("line\n" * 40),
                    )
                ],
            )

        if "what was" in lower or "original" in lower or "first search" in lower or "run_" in lower:
            needle = self._extract_needle(user_text)
            context_msgs = hot_messages[:-1] if hot_messages and hot_messages[-1].role == "user" else hot_messages
            context_text = "\n".join(f"{m.role}: {m.content}" for m in context_msgs)
            if needle and needle not in context_text:
                return LLMCompletion(
                    assistant_text=f"'{needle}' is not in my current window; searching archived segments.",
                    tool_calls=[
                        ToolCall(
                            name="recall_by_keyword",
                            arguments={"keyword": needle},
                        )
                    ],
                )
            return LLMCompletion(
                assistant_text=f"From current context: I still see information about '{needle or 'that'}' in the active window.",
                tool_calls=[],
            )

        return LLMCompletion(
            assistant_text=f"Acknowledged. (mock) Hot window has {len(hot_messages)} messages.",
            tool_calls=[],
        )

    @staticmethod
    def _extract_needle(user_text: str) -> str | None:
        for pattern in (
            r"trace[_\s-]?id[=:\s]+(\S+)",
            r"(RUN_\w+)",
            r"(TAIL_MARKER_ZZZ)",
            r"KEY_FINDING",
            r"FILE_CHUNK_\d+",
        ):
            if m := re.search(pattern, user_text, re.I):
                return m.group(0) if m.lastindex is None else m.group(1)
        return None

    @staticmethod
    def _span_blob(service: str, run: str, extra: str = "") -> str:
        payload = "x" * 1200
        tail = " TAIL_MARKER_ZZZ" if run == "RUN_A" else ""
        return f"SPAN[{service}] {run}{extra} {payload}{tail}"
