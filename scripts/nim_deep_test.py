#!/usr/bin/env python3
"""
Deep integration test: context policies + warm store + NVIDIA NIM (live API).

Phases:
  A — Programmatic stress (trim, archive, recall) — no API
  B — Live NIM turns with explicit tool/recall prompts
  C — Scripted observability demo (DEMO_SCRIPT) via real LLM

Usage:
  python scripts/nim_deep_test.py
  python scripts/nim_deep_test.py --phase b   # skip A/C
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openai import APITimeoutError

from context_manager.agent.llm_config import LLMConfig, load_dotenv_if_present
from context_manager.agent.llm_factory import llm_label
from context_manager.agent.loop import DEMO_SCRIPT, MinimalAgentLoop, run_scripted_demo
from context_manager.models import Message, TrimMode
from context_manager.session import ContextConfig, ContextSession


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class PhaseReport:
    phase: str
    checks: list[CheckResult] = field(default_factory=list)
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)


def _span(size: int, marker: str) -> str:
    filler = "x" * max(0, size - len(marker) - 24)
    return f"SPAN[payment-service] {marker} {filler}"


def phase_a_programmatic() -> PhaseReport:
    """Alex-style: many large tool results → archive → recall by keyword."""
    t0 = time.monotonic()
    checks: list[CheckResult] = []
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=1,
            tail_messages=6,
            tool_policy_enabled=True,
            preview_chars=100,
        )
    )
    try:
        session.append(Message("system", "Observability agent. Never drop system."))
        session.append(Message("user", "trace_id=checkout-failure-2026-03-15"))
        session.append(Message("assistant", "Searching spans."))
        for i in range(12):
            session.append(
                Message("tool", _span(4000, f"RUN_{i:02d}"), name="search_spans")
            )
        session.append(Message("user", "What was RUN_00?"))

        hot = session.get_hot_context()
        hot_text = "\n".join(m.content for m in hot)
        full_chars = session.total_chars()
        hot_chars = session.hot_char_count()
        archived = len(session.list_archived_segments())

        checks.append(
            CheckResult(
                "compression_ratio",
                hot_chars < full_chars * 0.85,
                f"hot={hot_chars} full={full_chars} ratio={hot_chars/full_chars:.1%}",
            )
        )
        checks.append(
            CheckResult("archived_segments", archived >= 4, f"archived={archived}")
        )
        checks.append(
            CheckResult(
                "latest_run_in_hot",
                "RUN_11" in hot_text,
                "latest tool result should stay in hot window",
            )
        )
        checks.append(
            CheckResult(
                "early_run_not_full_in_hot",
                _span(4000, "RUN_00") not in hot_text,
                "RUN_00 full blob should not be in hot",
            )
        )
        recalled = False
        for seg in session.list_archived_segments():
            if "RUN_00" in seg.content:
                body = session.recall(seg.id)
                recalled = body is not None and "RUN_00" in body
                break
        checks.append(
            CheckResult("recall_run_00", recalled, "warm store recall for RUN_00")
        )
        checks.append(
            CheckResult(
                "head_anchor_trace_id",
                "checkout-failure-2026-03-15" in hot_text,
                "turn-1 trace_id in head anchor",
            )
        )
    finally:
        session.close()

    return PhaseReport("A (programmatic)", checks, time.monotonic() - t0)


# Prompts designed to elicit tools + recall with real models
PHASE_B_TURNS: list[str] = [
    (
        "Use the search_spans tool now with query "
        "'trace_id=checkout-failure-2026-03-15 payment-service errors'. "
        "You must call search_spans before answering."
    ),
    "Which run had status 500 in the latest search results? Answer briefly.",
    "What was the original trace_id I asked about in turn 1?",
    (
        "The first search may be archived. Use recall_by_keyword with keyword "
        "'TAIL_MARKER_ZZZ' to retrieve it, then say what you found in one sentence."
    ),
    "Use the list_archived tool and report how many segments exist (approximate count).",
]


def phase_b_live_nim(cfg: LLMConfig) -> PhaseReport:
    t0 = time.monotonic()
    checks: list[CheckResult] = []
    results = []

    agent = MinimalAgentLoop(
        llm_config=cfg,
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=1,
            tail_messages=6,
            tool_policy_enabled=True,
            preview_chars=100,
        ),
        system_prompt=(
            "You are an observability debugging agent with tools: search_spans, "
            "read_file, recall_segment, recall_by_keyword, list_archived. "
            "When asked to use a tool, you MUST call it. Tool outputs can be large; "
            "older results are archived — use recall_by_keyword or recall_segment "
            "when the user asks about earlier data not in your current context."
        ),
    )
    try:
        for i, user_text in enumerate(PHASE_B_TURNS, 1):
            print(f"\n[B turn {i}/{len(PHASE_B_TURNS)}] {user_text[:90]}…")
            r = None
            for attempt in range(1, 4):
                try:
                    r = agent.run_turn(user_text)
                    break
                except APITimeoutError:
                    if attempt == 3:
                        raise
                    wait = 15 * attempt
                    print(f"  timeout (attempt {attempt}/3), retry in {wait}s…")
                    time.sleep(wait)
            assert r is not None
            results.append(r)
            tools = ", ".join(r.tool_names) or "(none)"
            print(
                f"  assistant: {r.assistant_text[:100]}…"
                if len(r.assistant_text) > 100
                else f"  assistant: {r.assistant_text}"
            )
            print(
                f"  tools={tools} | hot {r.hot_chars}/{r.full_chars} chars | "
                f"archived={r.archived_segments} recall={r.recall_happened}"
            )

        any_tools = any(r.tool_names for r in results)
        checks.append(
            CheckResult("llm_used_tools", any_tools, f"tool turns={[r.tool_names for r in results]}")
        )
        checks.append(
            CheckResult(
                "context_compressed",
                results[-1].hot_chars < results[-1].full_chars,
                f"hot={results[-1].hot_chars} full={results[-1].full_chars}",
            )
        )
        checks.append(
            CheckResult(
                "segments_archived",
                results[-1].archived_segments > 0,
                f"archived={results[-1].archived_segments}",
            )
        )
        checks.append(
            CheckResult(
                "recall_invoked",
                any(r.recall_happened for r in results),
                "at least one recall_by_keyword / recall_segment",
            )
        )
        hot_text = "\n".join(m.content for m in agent.session.get_hot_context())
        checks.append(
            CheckResult(
                "trace_id_in_hot_turn5",
                "checkout-failure-2026-03-15" in hot_text,
                "DeLucia head-anchor: original trace_id still in hot",
            )
        )
        total_prompt = sum(r.usage_prompt_tokens or 0 for r in results)
        total_completion = sum(r.usage_completion_tokens or 0 for r in results)
        checks.append(
            CheckResult(
                "token_usage_recorded",
                total_prompt > 0,
                f"prompt={total_prompt} completion={total_completion}",
            )
        )
    finally:
        agent.close()

    return PhaseReport("B (live NIM)", checks, time.monotonic() - t0)


def phase_c_demo_script(cfg: LLMConfig) -> PhaseReport:
    t0 = time.monotonic()
    checks: list[CheckResult] = []
    print("\n=== Phase C: DEMO_SCRIPT via NIM ===")
    results = run_scripted_demo(verbose=True, llm_config=cfg, user_lines=DEMO_SCRIPT)

    last = results[-1]
    checks.append(CheckResult("all_turns_complete", len(results) == len(DEMO_SCRIPT), f"{len(results)} turns"))
    checks.append(
        CheckResult(
            "compression",
            last.hot_chars < last.full_chars,
            f"hot={last.hot_chars} full={last.full_chars}",
        )
    )
    checks.append(
        CheckResult("archived", last.archived_segments > 0, f"archived={last.archived_segments}")
    )
    return PhaseReport("C (demo script)", checks, time.monotonic() - t0)


def print_report(report: PhaseReport) -> None:
    status = "PASS" if report.ok else "FAIL"
    print(f"\n--- Phase {report.phase}: {status} ({report.elapsed_s:.1f}s) ---")
    for c in report.checks:
        mark = "✓" if c.passed else "✗"
        print(f"  {mark} {c.name}: {c.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep NIM + context manager integration test")
    parser.add_argument(
        "--phase",
        choices=["all", "a", "b", "c"],
        default="all",
        help="Run subset of phases (default: all)",
    )
    args = parser.parse_args()

    load_dotenv_if_present()
    cfg = LLMConfig.from_env(provider="nim")
    if cfg.timeout_seconds < 300:
        cfg.timeout_seconds = 300.0
    if not cfg.resolved_api_key():
        print("ERROR: NVIDIA_API_KEY not set. Save .env in project root.", file=sys.stderr)
        return 1

    print("Deep test —", llm_label(cfg))
    reports: list[PhaseReport] = []

    if args.phase in ("all", "a"):
        reports.append(phase_a_programmatic())
        print_report(reports[-1])

    if args.phase in ("all", "b"):
        reports.append(phase_b_live_nim(cfg))
        print_report(reports[-1])

    if args.phase in ("all", "c"):
        reports.append(phase_c_demo_script(cfg))
        print_report(reports[-1])

    passed = sum(1 for r in reports if r.ok)
    print(f"\n=== Summary: {passed}/{len(reports)} phases passed ===")
    if not all(r.ok for r in reports):
        return 1
    print("Deep test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
