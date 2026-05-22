from pathlib import Path

import pytest

from context_manager.eval.harness import EvalCase, LongSessionEvaluator

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIRS = [
    ROOT / "fixtures",
    ROOT / "fixtures" / "realworld",
]


def _all_fixture_paths() -> list[Path]:
    paths: list[Path] = []
    for d in FIXTURE_DIRS:
        if d.is_dir():
            paths.extend(sorted(d.glob("*.json")))
    return paths


@pytest.mark.parametrize("path", _all_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_passes(path: Path):
    case = EvalCase.load(path)
    result = LongSessionEvaluator(case).run()
    assert result.passed, result.summary()
