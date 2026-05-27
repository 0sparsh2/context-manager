from context_manager.models import Message, TrimMode
from context_manager.session import ContextConfig, ContextSession


def test_tool_policy_keeps_latest_only():
    session = ContextSession.create(
        config=ContextConfig(trim_mode=TrimMode.HEAD_TAIL, tail_messages=20)
    )
    try:
        session.append(Message("tool", "OLD_RESULT", name="grep"))
        session.append(Message("tool", "NEW_RESULT_LATEST", name="grep"))
        hot = session.get_hot_context()
        text = "\n".join(m.content for m in hot)
        assert "NEW_RESULT_LATEST" in text
        assert not any(m.content == "OLD_RESULT" for m in hot)
        assert any(m.metadata.get("archived") for m in hot)
        segs = session.list_archived_segments()
        assert any("OLD_RESULT" in s.content for s in segs)
    finally:
        session.close()


def test_recall_archived_segment():
    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=1,
            tail_messages=1,
        )
    )
    try:
        session.append(Message("system", "sys"))
        session.append(Message("user", "KEEP_HEAD"))
        session.append(Message("user", "ARCHIVE_ME_MIDDLE"))
        session.append(Message("user", "KEEP_TAIL"))
        session.get_hot_context()
        seg = next(s for s in session.list_archived_segments() if "ARCHIVE_ME" in s.content)
        assert session.recall(seg.id) == "ARCHIVE_ME_MIDDLE"
    finally:
        session.close()


def test_metrics_hook_emits_trim_and_recall():
    events: list[tuple[str, dict]] = []

    def hook(name: str, fields: dict) -> None:
        events.append((name, fields))

    session = ContextSession.create(
        config=ContextConfig(
            trim_mode=TrimMode.HEAD_TAIL,
            head_messages=1,
            tail_messages=1,
            metrics_hook=hook,
        )
    )
    try:
        session.append(Message("system", "sys"))
        session.append(Message("user", "A"))
        session.append(Message("user", "B"))
        session.append(Message("assistant", "C"))
        session.get_hot_context()
        segs = session.list_archived_segments()
        if segs:
            session.recall(segs[0].id)
        names = [n for n, _ in events]
        assert "context.trim_applied" in names
        assert "context.recall_attempt" in names
    finally:
        session.close()
