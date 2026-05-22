#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || { python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" -q; }

echo "=== Unit + simulation tests ==="
pytest -q --tb=no

echo ""
echo "=== All fixture evals (fixtures/ + fixtures/realworld/) ==="
context-manager eval-all fixtures

echo ""
echo "=== Real-world inspect: observability session ==="
context-manager inspect fixtures/realworld/arize_observability_turn11.json

echo ""
echo "Done."
