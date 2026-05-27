from context_manager.memory.backends import NoneMemoryBackend, create_memory_backend


def test_none_backend_noop():
    backend = NoneMemoryBackend()
    backend.write_fact(session_id="s1", key="k", value="v")
    assert backend.read_fact(key="k") is None
    assert backend.enabled() is False


def test_default_factory_returns_none_backend(monkeypatch):
    monkeypatch.delenv("CONTEXT_MANAGER_MEMORY_BACKEND", raising=False)
    backend = create_memory_backend()
    assert backend.enabled() is False
