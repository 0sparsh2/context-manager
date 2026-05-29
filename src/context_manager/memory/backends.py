from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

from context_manager.errors import ErrorCode, ErrorEnvelope, MemoryBackendError


@dataclass
class MemoryFact:
    key: str
    value: str
    confidence: float = 1.0
    source: str = "session"
    session_id: str = ""
    created_at_unix: float = 0.0
    updated_at_unix: float = 0.0
    verified_at_unix: float = 0.0
    staleness_seconds: int = 0
    verification_status: str = "unverified"


class MemoryBackend(Protocol):
    def write_fact(self, *, session_id: str, key: str, value: str, source: str = "session") -> None: ...

    def read_fact(self, *, key: str) -> MemoryFact | None: ...

    def enabled(self) -> bool: ...


class NoneMemoryBackend:
    """No-op backend; preserves current behavior."""

    def write_fact(self, *, session_id: str, key: str, value: str, source: str = "session") -> None:
        return

    def read_fact(self, *, key: str) -> MemoryFact | None:
        return None

    def enabled(self) -> bool:
        return False


_INMEMORY_SINGLETON: InMemoryMemoryBackend | None = None


class InMemoryMemoryBackend:
    """Deterministic in-process backend for tests and local cross-session recall."""

    def __init__(self) -> None:
        self._facts: dict[str, MemoryFact] = {}

    def enabled(self) -> bool:
        return True

    def write_fact(
        self,
        *,
        session_id: str,
        key: str,
        value: str,
        source: str = "session",
    ) -> None:
        now = time.time()
        self._facts[key] = MemoryFact(
            key=key,
            value=value,
            session_id=session_id,
            source=source,
            confidence=1.0,
            created_at_unix=now,
            updated_at_unix=now,
            verified_at_unix=now,
            verification_status="verified",
        )

    def read_fact(self, *, key: str) -> MemoryFact | None:
        return self._facts.get(key)

    def list_facts(self, *, session_id: str | None = None) -> list[MemoryFact]:
        facts = list(self._facts.values())
        if session_id is None:
            return facts
        return [f for f in facts if f.session_id == session_id]


class Mem0PilotBackend:
    """
    Optional adapter with graceful fallback.
    Enabled only when CONTEXT_MANAGER_MEMORY_BACKEND=mem0.
    """

    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace or os.environ.get("CONTEXT_MANAGER_MEM0_NAMESPACE", "context-manager")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from mem0 import MemoryClient  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on optional extra
            raise MemoryBackendError(
                ErrorEnvelope(
                    code=ErrorCode.MEMORY,
                    message="Mem0 backend requested but mem0 package is unavailable.",
                    component="memory.mem0",
                    retryable=False,
                    boundary="memory_backend",
                )
            ) from exc
        api_key = os.environ.get("MEM0_API_KEY")
        self._client = MemoryClient(api_key=api_key) if api_key else MemoryClient()
        return self._client

    def write_fact(self, *, session_id: str, key: str, value: str, source: str = "session") -> None:
        try:
            client = self._get_client()
            client.add(
                [
                    {
                        "role": "user",
                        "content": f"{key}: {value}",
                    }
                ],
                user_id=session_id,
                metadata={"key": key, "source": source, "namespace": self.namespace},
            )
        except Exception as exc:
            raise MemoryBackendError(
                ErrorEnvelope(
                    code=ErrorCode.MEMORY,
                    message=f"Mem0 write failed: {exc.__class__.__name__}",
                    component="memory.mem0",
                    retryable=True,
                    boundary="memory_backend",
                )
            ) from exc

    def read_fact(self, *, key: str) -> MemoryFact | None:
        try:
            client = self._get_client()
            rows = client.search(query=key, top_k=1)
        except Exception as exc:
            raise MemoryBackendError(
                ErrorEnvelope(
                    code=ErrorCode.MEMORY,
                    message=f"Mem0 read failed: {exc.__class__.__name__}",
                    component="memory.mem0",
                    retryable=True,
                    boundary="memory_backend",
                )
            ) from exc
        if not rows:
            return None
        row = rows[0]
        content = str(row.get("memory") or row.get("text") or "")
        now = time.time()
        return MemoryFact(
            key=key,
            value=content,
            source="mem0",
            confidence=float(row.get("score", 0.7) or 0.7),
            created_at_unix=now,
            updated_at_unix=now,
            verified_at_unix=0.0,
            staleness_seconds=0,
            verification_status="unverified",
        )

    def enabled(self) -> bool:
        return True


def create_memory_backend() -> MemoryBackend:
    name = os.environ.get("CONTEXT_MANAGER_MEMORY_BACKEND", "none").strip().lower()
    if name in {"", "none", "off", "disabled"}:
        return NoneMemoryBackend()
    if name == "inmemory":
        global _INMEMORY_SINGLETON
        if _INMEMORY_SINGLETON is None:
            _INMEMORY_SINGLETON = InMemoryMemoryBackend()
        return _INMEMORY_SINGLETON
    if name == "mem0":
        try:
            return Mem0PilotBackend()
        except MemoryBackendError:
            return NoneMemoryBackend()
    return NoneMemoryBackend()


def memory_backend_status() -> dict[str, Any]:
    """Report configured backend and availability for operator diagnostics."""
    backend_name = os.environ.get("CONTEXT_MANAGER_MEMORY_BACKEND", "none").strip().lower()
    backend = create_memory_backend()
    status: dict[str, Any] = {
        "configured": backend_name,
        "enabled": backend.enabled(),
        "implementation": type(backend).__name__,
    }
    if backend_name == "mem0":
        status["mem0_api_key_present"] = bool(os.environ.get("MEM0_API_KEY"))
        try:
            status["mem0_sdk_available"] = Mem0PilotBackend().enabled()
        except MemoryBackendError:
            status["mem0_sdk_available"] = False
    return status
