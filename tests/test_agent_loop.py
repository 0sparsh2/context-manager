from context_manager.agent.loop import DEMO_SCRIPT, MinimalAgentLoop, run_scripted_demo
from context_manager.models import Message, TrimMode
from context_manager.session import ContextConfig


def test_agent_loop_scripted_demo_compression():
    results = run_scripted_demo(verbose=False)
    assert len(results) == len(DEMO_SCRIPT)
    last = results[-1]
    assert last.full_chars > last.hot_chars
    assert last.archived_segments > 0


def test_agent_loop_recalls_archived_content():
    lines = ["search trace_id=incident-42"]
    lines.extend(f"follow-up question {i}" for i in range(8))
    lines.append("What was TAIL_MARKER_ZZZ from the first search?")
    results = run_scripted_demo(verbose=False, user_lines=lines)
    assert any(r.recall_happened for r in results)


def test_turn_increments_and_appends_messages():
    agent = MinimalAgentLoop(system_prompt="sys")
    try:
        r1 = agent.run_turn("search spans for errors")
        r2 = agent.run_turn("what was RUN_LATEST?")
        assert r2.turn == 2
        assert r1.full_messages < r2.full_messages
        roles = [m.role for m in agent.session.messages]
        assert roles.count("tool") >= 1
    finally:
        agent.close()


def test_trace_id_survives_in_hot_after_many_turns():
    agent = MinimalAgentLoop(system_prompt="sys")
    try:
        for line in DEMO_SCRIPT[:3]:
            agent.run_turn(line)
        hot_text = "\n".join(m.content for m in agent.session.get_hot_context())
        assert "checkout-failure-2026-03-15" in hot_text
    finally:
        agent.close()


def test_recall_by_keyword_respects_scan_limit():
    cfg = ContextConfig(recall_scan_limit=1)
    agent = MinimalAgentLoop(system_prompt="sys", config=cfg)
    try:
        agent.run_turn("search trace_id=incident-42")
        # Force more archived content and move original marker out of newest segment.
        for i in range(6):
            agent.run_turn(f"filler {i}")
        r = agent.run_turn("What was TAIL_MARKER_ZZZ from the first search?")
        # With tight scan limit, recall is expected not to happen.
        assert r.recall_happened is False
    finally:
        agent.close()


def test_reported_full_chars_never_below_hot_chars():
    agent = MinimalAgentLoop(system_prompt="sys")
    try:
        r = agent.run_turn("search trace_id=incident-42")
        assert r.full_chars >= r.hot_chars
    finally:
        agent.close()
