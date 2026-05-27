#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from context_manager.eval.harness import EvalCase, LongSessionEvaluator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run benchmark-grade fixture gates")
    parser.add_argument("--fixtures", default="fixtures", help="Fixture directory")
    parser.add_argument("--min-quality", type=float, default=95.0)
    parser.add_argument("--max-latency-ms", type=float, default=50.0)
    parser.add_argument("--max-cost-usd", type=float, default=0.01)
    parser.add_argument("--json-out", default="benchmark-report.json")
    args = parser.parse_args()

    root = Path(args.fixtures)
    paths = sorted(root.rglob("*.json"))
    if not paths:
        print(f"No fixture files found in {root}")
        return 1

    rows: list[dict[str, object]] = []
    ok = True
    for path in paths:
        result = LongSessionEvaluator(EvalCase.load(path)).run()
        rows.append(
            {
                "fixture": str(path.relative_to(root)),
                "passed": result.passed,
                "quality_score": result.quality_score,
                "avg_turn_latency_ms": result.avg_turn_latency_ms,
                "estimated_cost_usd": result.estimated_cost_usd,
            }
        )
        if not result.passed:
            ok = False
        if result.quality_score < args.min_quality:
            ok = False
        if result.avg_turn_latency_ms > args.max_latency_ms:
            ok = False
        if result.estimated_cost_usd > args.max_cost_usd:
            ok = False

    report = {
        "budgets": {
            "min_quality": args.min_quality,
            "max_latency_ms": args.max_latency_ms,
            "max_cost_usd": args.max_cost_usd,
        },
        "results": rows,
    }
    Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
