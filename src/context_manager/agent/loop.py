from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from typing import Any

from context_manager.agent.llm_config import LLMConfig
from context_manager.agent.llm_factory import create_llm, llm_label
from context_manager.agent.openai_adapter import LLMClient
from context_manager.agent.types import LLMCompletion, ToolCall
from context_manager.models import Message
from context_manager.session import ContextConfig, ContextSession


@dataclass
class AgentTurnResult:
    turn: int
    user_text: str
    assistant_text: str
    tool_names: list[str]
    hot_messages: int
    hot_chars: int
    full_messages: int
    full_chars: int
    archived_segments: int
    recall_happened: bool = False
    notes: list[str] = field(default_factory=list)
    llm_rounds: int = 1
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None


class MinimalAgentLoop:
    """
    Minimal agent loop: user message → hot context → LLM → tools → transcript.

    The session holds the full transcript; the LLM only sees `get_hot_context()`.
    Real providers (OpenAI, NVIDIA NIM) use multi-round tool loops up to `max_tool_rounds`.
    """

    def __init__(
        self,
        session: ContextSession | None = None,
        llm: LLMClient | None = None,
        llm_config: LLMConfig | None = None,
        system_prompt: str | None = None,
        config: ContextConfig | None = None,
    ) -> None:
        self.session = session or ContextSession.create(config=config)
        self.llm_config = llm_config or LLMConfig(provider="mock")
        self.llm = llm or create_llm(self.llm_config)
        if system_prompt and not self.session.messages:
            self.session.append(Message("system", system_prompt))
        self._turn = 0

    def run_turn(self, user_text: str) -> AgentTurnResult:
        self._turn += 1
        self.session.append(Message("user", user_text))

        tool_names: list[str] = []
        notes: list[str] = []
        recall_happened = False
        assistant_parts: list[str] = []
        llm_rounds = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        has_usage = False

        max_rounds = self.llm_config.max_tool_rounds if self.llm_config.provider != "mock" else 1

        for _ in range(max_rounds):
            hot = self.session.get_hot_context()
            response = self.llm.complete(hot, user_text)
            llm_rounds += 1

            if response.usage_prompt_tokens is not None:
                total_prompt_tokens += response.usage_prompt_tokens
                has_usage = True
            if response.usage_completion_tokens is not None:
                total_completion_tokens += response.usage_completion_tokens
                has_usage = True

            if response.assistant_text:
                assistant_parts.append(response.assistant_text)

            if response.tool_calls:
                self._append_assistant_with_tools(response)
            elif response.assistant_text:
                self.session.append(Message("assistant", response.assistant_text))

            if not response.tool_calls:
                break

            for call in response.tool_calls:
                tool_names.append(call.name)
                content, recalled = self._execute_tool(call, notes)
                tc_id = call.id or f"{call.name}_{self._turn}_{llm_rounds}"
                self.session.append(
                    Message(
                        "tool",
                        content,
                        name=call.name,
                        tool_call_id=tc_id,
                    )
                )
                if recalled:
                    recall_happened = True

            if self.llm_config.provider == "mock":
                break

        if recall_happened and notes and self.llm_config.provider == "mock":
            summary = notes[-1]
            self.session.append(
                Message("assistant", f"Recalled from warm store: {summary[:500]}")
            )
            assistant_parts.append(f"Recalled from warm store: {summary[:500]}")

        hot_after = self.session.get_hot_context()
        return AgentTurnResult(
            turn=self._turn,
            user_text=user_text,
            assistant_text="\n".join(assistant_parts) if assistant_parts else "",
            tool_names=tool_names,
            hot_messages=len(hot_after),
            hot_chars=self.session.hot_char_count(),
            full_messages=len(self.session.messages),
            full_chars=self.session.total_chars(),
            archived_segments=len(self.session.list_archived_segments()),
            recall_happened=recall_happened,
            notes=notes,
            llm_rounds=llm_rounds,
            usage_prompt_tokens=total_prompt_tokens if has_usage else None,
            usage_completion_tokens=total_completion_tokens if has_usage else None,
        )

    def _append_assistant_with_tools(self, response: LLMCompletion) -> None:
        """Store assistant turn including tool_calls for OpenAI-compatible follow-ups."""
        meta: dict[str, Any] = {}
        if response.tool_calls:
            meta["tool_calls"] = [
                {
                    "id": tc.id or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for i, tc in enumerate(response.tool_calls)
            ]
        self.session.append(
            Message(
                "assistant",
                response.assistant_text or "",
                metadata=meta,
            )
        )

    def _execute_tool(self, call: ToolCall, notes: list[str]) -> tuple[str, bool]:
        if call.name == "recall_segment":
            seg_id = call.arguments.get("segment_id", "")
            body = self.session.recall(seg_id)
            if body is None:
                notes.append(f"segment {seg_id} not found")
                return f"ERROR: no segment {seg_id}", False
            notes.append(f"recalled {len(body)} chars from {seg_id}")
            return body, True

        if call.name == "list_archived":
            segs = self.session.list_archived_segments()
            lines = [f"- {s.id} pos={s.position} {s.preview}" for s in segs[:20]]
            if len(segs) > 20:
                lines.append(f"... and {len(segs) - 20} more")
            text = "\n".join(lines) or "(none)"
            return text, False

        if call.name == "recall_by_keyword":
            keyword = call.arguments.get("keyword", "")
            for seg in self.session.list_archived_segments():
                if keyword.lower() in seg.content.lower():
                    notes.append(f"found keyword in segment {seg.id}")
                    return seg.content, True
            return f"ERROR: keyword {keyword!r} not found in archive", False

        if call.name == "search_spans":
            if call.content:
                return call.content, False
            query = call.arguments.get("query", "")
            return self._stub_search_spans(query), False

        if call.name == "read_file":
            if call.content:
                return call.content, False
            path = call.arguments.get("path", "src/context_manager/session.py")
            return self._stub_read_file(path), False

        if call.content:
            return call.content, False

        return f"{call.name} completed", False

    @staticmethod
    def _stub_search_spans(query: str) -> str:
        payload = "x" * 1200
        return (
            f"SPAN[payment-service] RUN_LATEST status=500 {payload}\n"
            f"SPAN[auth-gateway] RUN_A {payload} TAIL_MARKER_ZZZ\n"
            f"(query={query!r})"
        )

    @staticmethod
    def _stub_read_file(path: str) -> str:
        return f"FILE:{path}\nKEY_FINDING: duplicate archive when policies stack\n" + ("line\n" * 40)

    def close(self) -> None:
        self.session.close()


# --- Scripted demo (observability-style session) ---

DEMO_SCRIPT: list[str] = [
    "Find errors in trace_id=checkout-failure-2026-03-15 across payment-service.",
    "Which run had status 500?",
    "What was the original trace_id I asked about?",
    "What was RUN_A from the first search?",
    "list archived segments",
]


def run_scripted_demo(
    *,
    verbose: bool = True,
    user_lines: list[str] | None = None,
    llm_config: LLMConfig | None = None,
) -> list[AgentTurnResult]:
    """
    Run a fixed multi-turn script showing context growth, trimming, and recall.

    Returns per-turn stats for tests and CLI output.
    """
    lines = user_lines or DEMO_SCRIPT
    cfg = llm_config or LLMConfig(provider="mock")
    agent = MinimalAgentLoop(
        llm_config=cfg,
        system_prompt=(
            "You are a minimal observability agent. Tools may return large span payloads. "
            "Use recall_segment or recall_by_keyword when the user asks about archived content."
        ),
    )
    results: list[AgentTurnResult] = []

    try:
        if verbose:
            print(f"LLM: {llm_label(cfg)}")
        for line in lines:
            result = agent.run_turn(line)
            results.append(result)
            if verbose:
                _print_turn(result)
        if verbose:
            _print_summary(results, cfg)
        return results
    finally:
        agent.close()


def _print_turn(r: AgentTurnResult) -> None:
    tools = ", ".join(r.tool_names) or "(none)"
    print(f"\n--- Turn {r.turn} ---")
    print(f"User: {r.user_text[:100]}{'…' if len(r.user_text) > 100 else ''}")
    print(f"Assistant: {r.assistant_text[:120]}")
    print(f"Tools: {tools}")
    print(
        f"Context: hot {r.hot_messages} msgs / {r.hot_chars} chars | "
        f"full {r.full_messages} msgs / {r.full_chars} chars | "
        f"archived {r.archived_segments}"
    )
    if r.llm_rounds > 1:
        print(f"LLM rounds: {r.llm_rounds}")
    if r.usage_prompt_tokens is not None:
        print(f"Tokens: prompt={r.usage_prompt_tokens} completion={r.usage_completion_tokens}")
    if r.recall_happened:
        print(f"Recall: {r.notes[-1] if r.notes else 'yes'}")


def _print_summary(results: list[AgentTurnResult], cfg: LLMConfig) -> None:
    if not results:
        return
    last = results[-1]
    ratio = last.hot_chars / last.full_chars if last.full_chars else 1.0
    print("\n=== Session summary ===")
    print(f"Turns: {len(results)}")
    print(f"Final hot/full char ratio: {ratio:.1%} ({last.hot_chars}/{last.full_chars})")
    print(f"Archived segments: {last.archived_segments}")
    llm_note = (
        "The LLM only received hot context each turn; full history lives in the session and warm store."
        if cfg.provider == "mock"
        else f"Provider {cfg.provider}: tool stubs execute locally; context trim/recall unchanged."
    )
    print(textwrap.fill(llm_note, width=72))


def run_interactive(llm_config: LLMConfig | None = None) -> None:
    """REPL demo: type user messages, see context stats each turn."""
    cfg = llm_config or LLMConfig(provider="mock")
    print(f"Minimal agent loop. LLM: {llm_label(cfg)}")
    print("Commands: /stats /hot /quit")
    agent = MinimalAgentLoop(
        llm_config=cfg,
        system_prompt="Minimal agent with context_manager session.",
    )
    try:
        while True:
            try:
                line = input("\nuser> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            if line in ("/quit", "/exit", "quit"):
                break
            if line == "/stats":
                print(
                    f"full={agent.session.total_chars()} hot={agent.session.hot_char_count()} "
                    f"archived={len(agent.session.list_archived_segments())}"
                )
                continue
            if line == "/hot":
                for i, m in enumerate(agent.session.get_hot_context()):
                    preview = m.content[:100].replace("\n", " ")
                    print(f"  [{i}] {m.role}: {preview}")
                continue
            _print_turn(agent.run_turn(line))
    finally:
        agent.close()
