from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCode(str, Enum):
    STORE = "E_STORE"
    MEMORY = "E_MEMORY"
    MEMORY_VERIFY = "E_MEMORY_VERIFY"
    LLM_TIMEOUT = "E_LLM_TIMEOUT"
    LLM_AUTH = "E_LLM_AUTH"
    LLM_PROVIDER = "E_LLM_PROVIDER"
    CONFIG = "E_CONFIG"


@dataclass
class ErrorEnvelope:
    code: str | ErrorCode
    message: str
    component: str
    retryable: bool
    boundary: str = "internal"

    def normalized_code(self) -> str:
        if isinstance(self.code, ErrorCode):
            return self.code.value
        return self.code


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

