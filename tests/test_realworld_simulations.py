"""
Programmatic real-world simulations (large payloads, high turn counts).
"""

from context_manager.models import Message, TrimMode
from context_manager.session import ContextConfig, ContextSession


def _span_dump(service: str, marker: str, size: int = 3500) -> str:
    filler = "x" * max(0, size - len(service) - len(marker) - 20)
    return f"SPAN[{service}] {marker} {filler}"


def test_realworld_massive_tool_spam_recall():
    """Replicate observability agent: 20 search_spans calls, only latest hot, first recallable."""
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=1,
            tail_messages=6,
            tool_policy_enabled=True,
        )
    )
    try:
        session.append(Message("system", "Observability agent."))
        session.append(Message("user", "trace_id=prod-incident-99"))
        session.append(Message("assistant", "Searching."))
        for i in range(20):
            marker = f"RUN_{i:02d}"
            session.append(
                Message("tool", _span_dump("payment", marker), name="search_spans")
            )
        session.append(Message("user", "What was RUN_00?"))
        hot = session.get_hot_context()
        hot_text = "\n".join(m.content for m in hot)
        assert "RUN_19" in hot_text
        assert "RUN_00" not in hot_text or all(
            m.content != _span_dump("payment", "RUN_00") for m in hot
        )
        seg = next(s for s in session.list_archived_segments() if "RUN_00" in s.content)
        assert "RUN_00" in (session.recall(seg.id) or "")
    finally:
        session.close()


def test_realworld_deLucia_exact_turn_11():
    """10 conversational turns then turn-11 question about turn-1 topic."""
    session = ContextSession.create(
        config=ContextConfig(trim_mode=TrimMode.HEAD_TAIL, head_messages=1, tail_messages=5)
    )
    try:
        session.append(Message("system", "Alex."))
        session.append(Message("user", "PRIMARY_GOAL: reduce checkout latency P99"))
        for i in range(2, 11):
            session.append(Message("assistant", f"working step {i}"))
            session.append(Message("user", f"filler question {i}"))
        session.append(Message("user", "What was PRIMARY_GOAL?"))
        hot = session.get_hot_context()
        assert any("PRIMARY_GOAL" in m.content for m in hot)
    finally:
        session.close()


def test_realworld_cursor_50_file_reads():
    """Cursor-like: 50 read_file results; ask about content from read #3."""
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=2,
            tail_messages=8,
            tool_policy_enabled=True,
        )
    )
    try:
        session.append(Message("system", "Coding agent."))
        session.append(Message("user", "Refactor module X"))
        session.append(Message("assistant", "Reading."))
        for i in range(50):
            marker = f"FILE_CHUNK_{i:03d}"
            session.append(Message("tool", f"content of {marker}", name="read_file"))
        session.append(Message("user", "What was in FILE_CHUNK_003?"))
        hot = session.get_hot_context()
        hot_text = "\n".join(m.content for m in hot)
        assert "FILE_CHUNK_049" in hot_text
        seg = next(s for s in session.list_archived_segments() if "FILE_CHUNK_003" in s.content)
        assert session.recall(seg.id) is not None
    finally:
        session.close()


def test_realworld_compression_ratio():
    """Hot context should be materially smaller than full transcript for spammy sessions."""
    session = ContextSession.create(
        config=ContextConfig(trim_mode=TrimMode.HEAD_TAIL, tail_messages=6, tool_policy_enabled=True)
    )
    try:
        session.append(Message("user", "analyze"))
        for _ in range(30):
            session.append(Message("tool", "x" * 5000, name="grep"))
        full = session.total_chars()
        hot = session.hot_char_count()
        assert hot < full * 0.5, f"expected compression, got hot={hot} full={full}"
    finally:
        session.close()
