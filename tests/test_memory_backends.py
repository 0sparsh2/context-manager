from context_manager.memory.backends import InMemoryMemoryBackend, NoneMemoryBackend, create_memory_backend


def test_none_backend_noop():
    backend = NoneMemoryBackend()
    backend.write_fact(session_id="s1", key="k", value="v")
    assert backend.read_fact(key="k") is None
    assert backend.enabled() is False


def test_default_factory_returns_none_backend(monkeypatch):
    monkeypatch.delenv("CONTEXT_MANAGER_MEMORY_BACKEND", raising=False)
    backend = create_memory_backend()
    assert backend.enabled() is False


def test_inmemory_backend_enabled(monkeypatch):
    monkeypatch.setenv("CONTEXT_MANAGER_MEMORY_BACKEND", "inmemory")
    backend = create_memory_backend()
    assert isinstance(backend, InMemoryMemoryBackend)
    assert backend.enabled() is True
    backend.write_fact(session_id="s1", key="tenant", value="acme")
    fact = backend.read_fact(key="tenant")
    assert fact is not None
    assert fact.value == "acme"


def test_memory_backend_status(monkeypatch):
    from context_manager.memory.backends import memory_backend_status

    monkeypatch.delenv("CONTEXT_MANAGER_MEMORY_BACKEND", raising=False)
    status = memory_backend_status()
    assert status["configured"] == "none"
    assert status["enabled"] is False
