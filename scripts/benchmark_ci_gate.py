#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from context_manager.eval.benchmarks import dynamic_budget_for_case, evaluate_result
from context_manager.eval.harness import EvalCase, LongSessionEvaluator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark-grade fixture gates")
    parser.add_argument("--fixtures", default="fixtures", help="Fixture directory")
    parser.add_argument("--min-quality", type=float, default=95.0)
    parser.add_argument("--max-latency-ms", type=float, default=50.0)
    parser.add_argument("--max-cost-usd", type=float, default=0.01)
    parser.add_argument(
        "--dynamic-budgets",
        action="store_true",
        help="Use per-fixture budgets scaled by turn/assertion complexity",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Optional prior benchmark-report.json for regression comparison",
    )
    parser.add_argument("--json-out", default="benchmark-report.json")
    args = parser.parse_args()

    root = Path(args.fixtures)
    paths = sorted(root.rglob("*.json"))
    if not paths:
        print(f"No fixture files found in {root}")
        return 1

    baseline: dict[str, dict[str, object]] = {}
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            prior = json.loads(baseline_path.read_text(encoding="utf-8"))
            for row in prior.get("results", []):
                baseline[str(row.get("fixture"))] = row

    checks: list[dict[str, object]] = []
    ok = True
    for path in paths:
        case = EvalCase.load(path)
        result = LongSessionEvaluator(case).run()
        rel = str(path.relative_to(root))
        if args.dynamic_budgets:
            budget = dynamic_budget_for_case(case)
            check = evaluate_result(
                fixture_name=rel,
                result=result,
                turn_latencies_ms=result.turn_latencies_ms,
                budget=budget,
            )
            checks.append(check.as_dict())
            if not check.passed:
                ok = False
        else:
            failures: list[str] = []
            if not result.passed:
                failures.append("fixture assertions failed")
            if result.quality_score < args.min_quality:
                failures.append(
                    f"quality {result.quality_score:.1f} < min {args.min_quality:.1f}"
                )
            if result.avg_turn_latency_ms > args.max_latency_ms:
                failures.append(
                    f"avg latency {result.avg_turn_latency_ms:.2f}ms > max {args.max_latency_ms:.2f}ms"
                )
            if result.estimated_cost_usd > args.max_cost_usd:
                failures.append(f"cost ${result.estimated_cost_usd:.6f} > max ${args.max_cost_usd:.6f}")
            checks.append(
                {
                    "fixture": rel,
                    "passed": not failures,
                    "failures": failures,
                    "metrics": {
                        "passed": result.passed,
                        "quality_score": result.quality_score,
                        "avg_turn_latency_ms": result.avg_turn_latency_ms,
                        "p95_turn_latency_ms": result.p95_turn_latency_ms,
                        "estimated_cost_usd": result.estimated_cost_usd,
                    },
                }
            )
            if failures:
                ok = False

        prior = baseline.get(rel)
        if prior is not None:
            prior_quality = float(prior.get("quality_score", prior.get("metrics", {}).get("quality_score", 100)))
            current_quality = result.quality_score
            if current_quality + 5 < prior_quality:
                ok = False
                checks[-1]["regression"] = {
                    "quality_drop": prior_quality - current_quality,
                    "prior_quality": prior_quality,
                    "current_quality": current_quality,
                }

    report = {
        "mode": "dynamic" if args.dynamic_budgets else "fixed",
        "budgets": {
            "min_quality": args.min_quality,
            "max_latency_ms": args.max_latency_ms,
            "max_cost_usd": args.max_cost_usd,
        },
        "results": checks,
    }
    Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
