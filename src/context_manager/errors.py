from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ErrorEnvelope:
    code: str
    message: str
    component: str
    retryable: bool


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

