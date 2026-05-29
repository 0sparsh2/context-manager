from context_manager.eval.benchmarks import dynamic_budget_for_case, evaluate_result, p95
from context_manager.eval.harness import EvalCase, EvalResult, LongSessionEvaluator
from context_manager.memory.backends import InMemoryMemoryBackend, create_memory_backend
from context_manager.memory.verification import MemoryVerificationPolicy, verify_memory_fact
from context_manager.models import Message
from context_manager.session import ContextConfig, ContextSession
import os
import time


def test_p95_helper():
    assert p95([1.0, 2.0, 3.0, 4.0, 100.0]) >= 4.0


def test_dynamic_budget_scales_with_turns(tmp_path):
    case = EvalCase.from_dict(
        {
            "name": "tiny",
            "config": {},
            "turns": [[{"role": "user", "content": "hi"}]],
            "assertions": [],
        }
    )
    budget = dynamic_budget_for_case(case)
    assert budget.turn_count == 1
    assert budget.max_avg_latency_ms < 100


def test_evaluate_result_flags_latency_regression():
    case = EvalCase.from_dict(
        {
            "name": "x",
            "config": {},
            "turns": [[{"role": "user", "content": "a"}]],
            "assertions": [],
        }
    )
    budget = dynamic_budget_for_case(case)
    result = EvalResult(case_name="x", passed=True, quality_score=100.0, avg_turn_latency_ms=999.0)
    check = evaluate_result(
        fixture_name="x.json",
        result=result,
        turn_latencies_ms=[999.0],
        budget=budget,
    )
    assert check.passed is False
    assert any("latency" in f for f in check.failures)


def test_inmemory_backend_cross_session(monkeypatch):
    monkeypatch.setenv("CONTEXT_MANAGER_MEMORY_BACKEND", "inmemory")
    backend = create_memory_backend()
    assert isinstance(backend, InMemoryMemoryBackend)
    s1 = ContextSession.create()
    s2 = ContextSession.create()
    try:
        s1.append(Message(role="user", content="project: context-manager"))
        value = s2.recall_from_memory("project")
        assert value == "context-manager"
    finally:
        s1.close()
        s2.close()


def test_memory_verification_blocks_stale(monkeypatch):
    from context_manager.memory.backends import MemoryFact

    old = time.time() - 100000
    fact = MemoryFact(
        key="k",
        value="v",
        confidence=1.0,
        created_at_unix=old,
        verified_at_unix=old,
    )
    decision = verify_memory_fact(
        fact,
        policy=MemoryVerificationPolicy(require_verified=False, max_age_seconds=60),
    )
    assert decision.allowed is False
    assert decision.reason == "stale"


def test_memory_verification_blocks_unverified():
    from context_manager.memory.backends import MemoryFact

    fact = MemoryFact(key="k", value="v", confidence=1.0, created_at_unix=time.time(), verified_at_unix=0.0)
    decision = verify_memory_fact(
        fact,
        policy=MemoryVerificationPolicy(require_verified=True, max_age_seconds=3600),
    )
    assert decision.allowed is False
    assert decision.reason == "unverified"


def test_memory_diagnostics(monkeypatch):
    monkeypatch.setenv("CONTEXT_MANAGER_MEMORY_BACKEND", "inmemory")
    session = ContextSession.create()
    try:
        session.append(Message(role="user", content="color: blue"))
        diag = session.memory_diagnostics("color")
        assert diag["hit"] is True
        assert diag["allowed"] is True
    finally:
        session.close()


def test_harness_reports_p95(tmp_path):
    fixture = tmp_path / "p95.json"
    fixture.write_text(
        """{
  "name": "p95",
  "config": {},
  "turns": [
    [{"role": "user", "content": "one"}],
    [{"role": "user", "content": "two"}]
  ],
  "assertions": []
}""",
        encoding="utf-8",
    )
    result = LongSessionEvaluator(EvalCase.load(fixture)).run()
    assert len(result.turn_latencies_ms) == 2
    assert result.p95_turn_latency_ms >= min(result.turn_latencies_ms)
