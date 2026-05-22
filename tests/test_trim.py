from context_manager.models import Message
from context_manager.policies.trim import HeadTailTrimPolicy, LastNTrimPolicy
from context_manager.store.sqlite import SQLiteSegmentStore


def test_last_n_archives_old_messages():
    store = SQLiteSegmentStore()
    policy = LastNTrimPolicy(keep_last=2)
    msgs = [
        Message("system", "sys"),
        Message("user", "first"),
        Message("assistant", "a1"),
        Message("user", "second"),
        Message("assistant", "a2"),
    ]
    hot = policy.apply(
        msgs,
        session_id="s1",
        position_offset=0,
        save_segment=store.save,
        preview_chars=40,
    )
    assert any("first" in m.content or m.metadata.get("archived") for m in hot)
    assert hot[-1].content == "a2"
    store.close()


def test_head_tail_keeps_anchors():
    store = SQLiteSegmentStore()
    policy = HeadTailTrimPolicy(head_messages=1, tail_messages=2)
    msgs = [
        Message("system", "sys"),
        Message("user", "HEAD_ANCHOR"),
        Message("user", "m2"),
        Message("user", "m3"),
        Message("user", "TAIL_ONE"),
        Message("user", "TAIL_TWO"),
    ]
    hot = policy.apply(
        msgs,
        session_id="s1",
        position_offset=0,
        save_segment=store.save,
        preview_chars=40,
    )
    contents = " ".join(m.content for m in hot)
    assert "HEAD_ANCHOR" in contents
    assert "TAIL_TWO" in contents
    assert any(m.metadata.get("archived") for m in hot)
    store.close()
