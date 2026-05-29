from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from context_manager.memory.backends import MemoryFact


@dataclass
class MemoryVerificationPolicy:
    require_verified: bool = False
    max_age_seconds: int = 60 * 60 * 24 * 14
    min_confidence: float = 0.0


@dataclass
class MemoryVerificationResult:
    allowed: bool
    reason: str
    reason_codes: list[str]
    age_seconds: int
    confidence: float
    verified: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "reason_codes": self.reason_codes,
            "age_seconds": self.age_seconds,
            "confidence": self.confidence,
            "verified": self.verified,
        }


def verify_memory_fact(
    fact: MemoryFact | None,
    *,
    policy: MemoryVerificationPolicy,
) -> MemoryVerificationResult:
    if fact is None:
        return MemoryVerificationResult(
            allowed=False,
            reason="not_found",
            reason_codes=["E_MEMORY_NOT_FOUND"],
            age_seconds=-1,
            confidence=0.0,
            verified=False,
        )
    now = time.time()
    age_seconds = max(0, int(now - fact.created_at_unix))
    verified = bool(fact.verified_at_unix and fact.verified_at_unix > 0)
    is_fresh = age_seconds <= policy.max_age_seconds
    confidence_ok = fact.confidence >= policy.min_confidence
    reason_codes: list[str] = []
    if policy.require_verified and not verified:
        return MemoryVerificationResult(
            allowed=False,
            reason="unverified",
            reason_codes=["E_MEMORY_VERIFY"],
            age_seconds=age_seconds,
            confidence=fact.confidence,
            verified=verified,
        )
    if not is_fresh:
        return MemoryVerificationResult(
            allowed=False,
            reason="stale",
            reason_codes=["E_MEMORY_VERIFY"],
            age_seconds=age_seconds,
            confidence=fact.confidence,
            verified=verified,
        )
    if not confidence_ok:
        return MemoryVerificationResult(
            allowed=False,
            reason="low_confidence",
            reason_codes=["E_MEMORY_VERIFY"],
            age_seconds=age_seconds,
            confidence=fact.confidence,
            verified=verified,
        )
    reason_codes.append("OK")
    return MemoryVerificationResult(
        allowed=True,
        reason="ok",
        reason_codes=reason_codes,
        age_seconds=age_seconds,
        confidence=fact.confidence,
        verified=verified,
    )
