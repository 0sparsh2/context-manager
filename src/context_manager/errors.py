from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    STORE = "E_STORE"
    MEMORY = "E_MEMORY"
    MEMORY_VERIFY = "E_MEMORY_VERIFY"
    LLM_TIMEOUT = "E_LLM_TIMEOUT"
    LLM_AUTH = "E_LLM_AUTH"
    LLM_PROVIDER = "E_LLM_PROVIDER"
    CONFIG = "E_CONFIG"


class ErrorBoundary(str, Enum):
    INTERNAL = "internal"
    PROVIDER_ADAPTER = "provider_adapter"
    STORAGE = "storage"
    MEMORY_BACKEND = "memory_backend"
    CLI = "cli"


@dataclass
class ErrorEnvelope:
    code: str | ErrorCode
    message: str
    component: str
    retryable: bool
    boundary: str | ErrorBoundary = ErrorBoundary.INTERNAL

    def normalized_code(self) -> str:
        if isinstance(self.code, ErrorCode):
            return self.code.value
        return self.code

    def normalized_boundary(self) -> str:
        if isinstance(self.boundary, ErrorBoundary):
            return self.boundary.value
        return self.boundary

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.normalized_code(),
            "message": self.message,
            "component": self.component,
            "retryable": self.retryable,
            "boundary": self.normalized_boundary(),
        }


class ContextManagerError(Exception):
    def __init__(self, envelope: ErrorEnvelope) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope


class StoreError(ContextManagerError):
    pass


class LLMTimeoutError(ContextManagerError):
    pass


class LLMAuthError(ContextManagerError):
    pass


class LLMProviderError(ContextManagerError):
    pass


class MemoryBackendError(ContextManagerError):
    pass


class MemoryVerificationError(ContextManagerError):
    pass

