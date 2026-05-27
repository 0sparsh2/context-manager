from pathlib import Path

from context_manager.eval.harness import EvalCase, LongSessionEvaluator

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_tool_spam_fixture_passes():
    case = EvalCase.load(FIXTURES / "tool_spam_then_followup.json")
    result = LongSessionEvaluator(case).run()
    assert result.passed, result.summary()


def test_naive_truncation_fixture_passes():
    case = EvalCase.load(FIXTURES / "naive_truncation_fails.json")
    result = LongSessionEvaluator(case).run()
    assert result.passed, result.summary()


def test_eval_result_exposes_quality_latency_cost():
    case = EvalCase.load(FIXTURES / "tool_spam_then_followup.json")
    result = LongSessionEvaluator(case).run()
    assert result.quality_score > 0
    assert result.avg_turn_latency_ms >= 0
    assert result.estimated_prompt_tokens >= 0
    assert result.estimated_cost_usd >= 0
