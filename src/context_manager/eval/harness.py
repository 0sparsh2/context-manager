from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from context_manager.models import Message
from context_manager.session import ContextConfig, ContextSession


@dataclass
class TurnAssertion:
    """Checks after applying context through turn `after_turn` (1-based)."""

    after_turn: int
    kind: Literal[
        "content_in_hot",
        "content_not_in_hot",
        "content_recallable",
        "hot_chars_under",
        "archived_count_at_least",
    ]
    value: str | int
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnAssertion:
        return cls(
            after_turn=int(data["after_turn"]),
            kind=data["kind"],
            value=data.get("value", ""),
            description=data.get("description", ""),
        )


@dataclass
class EvalCase:
    name: str
    config: dict[str, Any]
    turns: list[list[dict[str, Any]]]
    assertions: list[TurnAssertion]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalCase:
        return cls(
            name=data["name"],
            config=data.get("config", {}),
            turns=data["turns"],
            assertions=[TurnAssertion.from_dict(a) for a in data.get("assertions", [])],
        )

    @classmethod
    def load(cls, path: str | Path) -> EvalCase:
        with Path(path).open(encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


@dataclass
class AssertionResult:
    assertion: TurnAssertion
    passed: bool
    detail: str


@dataclass
class EvalResult:
    case_name: str
    passed: bool
    assertion_results: list[AssertionResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Case: {self.case_name} — {'PASS' if self.passed else 'FAIL'}"]
        for ar in self.assertion_results:
            mark = "✓" if ar.passed else "✗"
            lines.append(f"  {mark} turn {ar.assertion.after_turn} {ar.assertion.kind}: {ar.detail}")
        return "\n".join(lines)


class LongSessionEvaluator:
    """
    Alex-style long-session eval: replay turns 1..N, then check assertions
    (often configured for turn N+1 / `after_turn`).
    """

    def __init__(self, case: EvalCase) -> None:
        self.case = case

    def _build_config(self) -> ContextConfig:
        c = self.case.config
        trim_mode = c.get("trim_mode", "head_tail")
        from context_manager.models import TrimMode

        return ContextConfig(
            trim_mode=TrimMode(trim_mode) if isinstance(trim_mode, str) else trim_mode,
            keep_last_n=int(c.get("keep_last_n", 12)),
            head_messages=int(c.get("head_messages", 1)),
            tail_messages=int(c.get("tail_messages", 6)),
            preview_chars=int(c.get("preview_chars", 80)),
            tool_policy_enabled=bool(c.get("tool_policy_enabled", True)),
            db_path=c.get("db_path"),
        )

    def run(self) -> EvalResult:
        session = ContextSession.create(config=self._build_config())
        results: list[AssertionResult] = []

        try:
            assertions_by_turn: dict[int, list[TurnAssertion]] = {}
            for a in self.case.assertions:
                assertions_by_turn.setdefault(a.after_turn, []).append(a)

            for turn_idx, turn_messages in enumerate(self.case.turns, start=1):
                for raw in turn_messages:
                    session.append(Message.from_dict(raw))

                for assertion in assertions_by_turn.get(turn_idx, []):
                    results.append(self._check(session, assertion))

            passed = all(r.passed for r in results)
            return EvalResult(
                case_name=self.case.name,
                passed=passed,
                assertion_results=results,
            )
        finally:
            session.close()

    def _check(self, session: ContextSession, assertion: TurnAssertion) -> AssertionResult:
        hot = session.get_hot_context()
        hot_text = "\n".join(m.content for m in hot)
        kind = assertion.kind
        value = assertion.value

        if kind == "content_in_hot":
            ok = str(value) in hot_text
            detail = f"expected in hot context: {value!r}"
        elif kind == "content_not_in_hot":
            ok = str(value) not in hot_text
            detail = f"expected absent from hot context: {value!r}"
        elif kind == "content_recallable":
            # value is substring that must exist in some archived segment and be recallable
            needle = str(value)
            found_id: str | None = None
            for seg in session.list_archived_segments():
                if needle in seg.content:
                    found_id = seg.id
                    break
            if found_id is None:
                ok = False
                detail = f"no segment contains {needle!r}"
            else:
                recalled = session.recall(found_id)
                ok = recalled is not None and needle in recalled
                detail = f"recall segment {found_id}: {needle!r}"
        elif kind == "hot_chars_under":
            limit = int(value)
            count = session.hot_char_count()
            ok = count < limit
            detail = f"hot chars {count} < {limit}"
        elif kind == "archived_count_at_least":
            need = int(value)
            count = len(session.list_archived_segments())
            ok = count >= need
            detail = f"archived segments {count} >= {need}"
        else:
            ok = False
            detail = f"unknown assertion kind {kind}"

        if not ok and assertion.description:
            detail = f"{assertion.description} — {detail}"

        return AssertionResult(assertion=assertion, passed=ok, detail=detail)
