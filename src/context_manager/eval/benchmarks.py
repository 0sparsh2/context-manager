from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from context_manager.eval.harness import EvalCase, EvalResult


@dataclass
class FixtureBudget:
    """Dynamic budget derived from fixture complexity."""

    min_quality: float
    max_avg_latency_ms: float
    max_p95_latency_ms: float
    max_cost_usd: float
    turn_count: int
    assertion_count: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "min_quality": self.min_quality,
            "max_avg_latency_ms": self.max_avg_latency_ms,
            "max_p95_latency_ms": self.max_p95_latency_ms,
            "max_cost_usd": self.max_cost_usd,
            "turn_count": self.turn_count,
            "assertion_count": self.assertion_count,
        }


@dataclass
class BudgetCheckResult:
    fixture: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    budget: FixtureBudget | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture,
            "passed": self.passed,
            "failures": self.failures,
            "budget": self.budget.as_dict() if self.budget else None,
            "metrics": self.metrics,
        }


def dynamic_budget_for_case(case: EvalCase) -> FixtureBudget:
    """
    Scale budgets with fixture complexity instead of one global threshold.

    - More turns -> slightly higher latency allowance
    - More assertions -> stricter quality floor stays at 95+
    - Cost scales with transcript size proxy (turn count)
    """
    turns = len(case.turns)
    assertions = len(case.assertions)
    base_latency = 50.0
    per_turn_latency = 8.0
    max_avg = base_latency + (turns * per_turn_latency)
    max_p95 = max_avg * 2.5
    max_cost = min(0.05, 0.002 + (turns * 0.0008))
    min_quality = 95.0 if assertions >= 2 else 90.0
    return FixtureBudget(
        min_quality=min_quality,
        max_avg_latency_ms=max_avg,
        max_p95_latency_ms=max_p95,
        max_cost_usd=max_cost,
        turn_count=turns,
        assertion_count=assertions,
    )


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    idx = int(round(0.95 * (len(sorted_vals) - 1)))
    return sorted_vals[idx]


def evaluate_result(
    *,
    fixture_name: str,
    result: EvalResult,
    turn_latencies_ms: list[float],
    budget: FixtureBudget,
) -> BudgetCheckResult:
    p95_latency = p95(turn_latencies_ms)
    failures: list[str] = []
    if not result.passed:
        failures.append("fixture assertions failed")
    if result.quality_score < budget.min_quality:
        failures.append(
            f"quality {result.quality_score:.1f} < min {budget.min_quality:.1f}"
        )
    if result.avg_turn_latency_ms > budget.max_avg_latency_ms:
        failures.append(
            f"avg latency {result.avg_turn_latency_ms:.2f}ms > max {budget.max_avg_latency_ms:.2f}ms"
        )
    if p95_latency > budget.max_p95_latency_ms:
        failures.append(
            f"p95 latency {p95_latency:.2f}ms > max {budget.max_p95_latency_ms:.2f}ms"
        )
    if result.estimated_cost_usd > budget.max_cost_usd:
        failures.append(
            f"cost ${result.estimated_cost_usd:.6f} > max ${budget.max_cost_usd:.6f}"
        )
    return BudgetCheckResult(
        fixture=fixture_name,
        passed=not failures,
        failures=failures,
        budget=budget,
        metrics={
            "passed": result.passed,
            "quality_score": result.quality_score,
            "avg_turn_latency_ms": result.avg_turn_latency_ms,
            "p95_turn_latency_ms": p95_latency,
            "estimated_cost_usd": result.estimated_cost_usd,
            "estimated_prompt_tokens": result.estimated_prompt_tokens,
            "estimated_completion_tokens": result.estimated_completion_tokens,
        },
    )
