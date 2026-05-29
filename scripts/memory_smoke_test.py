#!/usr/bin/env python3
"""Smoke test for optional memory backends (Mem0 pilot). Skips when not configured."""
from __future__ import annotations

import os
import sys

from context_manager.memory.backends import InMemoryMemoryBackend, create_memory_backend, memory_backend_status
from context_manager.memory.verification import MemoryVerificationPolicy, verify_memory_fact
from context_manager.models import Message
from context_manager.session import ContextSession


def test_inmemory_cross_session() -> None:
    os.environ["CONTEXT_MANAGER_MEMORY_BACKEND"] = "inmemory"
    s1 = ContextSession.create()
    try:
        s1.append(Message(role="user", content="tenant: acme"))
        s2 = ContextSession.create()
        value = s2.recall_from_memory("tenant")
        assert value == "acme", f"expected acme, got {value!r}"
        diag = s2.memory_diagnostics("tenant")
        assert diag["allowed"] is True
    finally:
        s1.close()
        s2.close()
        os.environ.pop("CONTEXT_MANAGER_MEMORY_BACKEND", None)


def test_mem0_if_configured() -> None:
    if os.environ.get("CONTEXT_MANAGER_MEMORY_BACKEND", "").lower() != "mem0":
        print("SKIP mem0: CONTEXT_MANAGER_MEMORY_BACKEND != mem0")
        return
    if not os.environ.get("MEM0_API_KEY"):
        print("SKIP mem0: MEM0_API_KEY not set")
        return
    backend = create_memory_backend()
    if not backend.enabled():
        print("SKIP mem0: backend not enabled")
        return
    session_id = "memory-smoke-test"
    key = "smoke_key"
    value = "smoke_value"
    backend.write_fact(session_id=session_id, key=key, value=value, source="smoke")
    fact = backend.read_fact(key=key)
    assert fact is not None, "mem0 read returned None after write"
    decision = verify_memory_fact(
        fact,
        policy=MemoryVerificationPolicy(require_verified=False, max_age_seconds=3600),
    )
    print(f"mem0 smoke OK: reason={decision.reason} confidence={decision.confidence}")


def main() -> int:
    print("memory backend status:", memory_backend_status())
    test_inmemory_cross_session()
    print("inmemory cross-session: PASS")
    try:
        test_mem0_if_configured()
    except Exception as exc:
        print(f"mem0 smoke FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
