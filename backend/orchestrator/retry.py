"""
Retry policy: how many times a stage is attempted and how long to wait
between attempts (exponential backoff, capped).

Example with backoff_base=2.0: wait 2s after the 1st failure, 4s after
the 2nd, 8s after the 3rd ... never more than max_backoff.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .stages import AGGREGATION, ANALYSIS_STAGES, COLLECTION, SECURITY


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_base: float = 1.0   # seconds
    max_backoff: float = 30.0   # seconds

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_base < 0 or self.max_backoff < 0:
            raise ValueError("backoff values cannot be negative")

    def delay_after(self, failed_attempt: int) -> float:
        """Seconds to wait after attempt number `failed_attempt` fails."""
        return min(self.backoff_base * (2 ** (failed_attempt - 1)), self.max_backoff)


def default_policies() -> Dict[str, RetryPolicy]:
    """
    Starting values — open for team discussion (design doc, Section 5).

    Collection gets the most retries because its failures are usually
    network problems that clear up on their own. Analysis stages retry
    once and then rely on a fallback agent where one is registered.
    """
    policies = {
        COLLECTION: RetryPolicy(max_attempts=3, backoff_base=2.0),
        SECURITY: RetryPolicy(max_attempts=2, backoff_base=1.0),
        AGGREGATION: RetryPolicy(max_attempts=2, backoff_base=1.0),
    }
    for stage in ANALYSIS_STAGES:
        policies[stage] = RetryPolicy(max_attempts=2, backoff_base=1.0)
    return policies
