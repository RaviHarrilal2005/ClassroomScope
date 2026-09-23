"""
The contract every pipeline agent follows, plus stub agents.

AGENT CONTRACT
--------------
An agent is any object with a `name` and a `run(ctx)` method.

  * `run` receives a RunContext (run_id + article IDs, never article text).
  * The agent reads the data it needs from the database itself and
    writes its own results to its own table (e.g. sentiment_results).
  * `run` returns a small summary dict (see EXPECTED OUTPUT below).
  * To signal failure, the agent raises an exception. The coordinator
    catches it and applies retry / fallback rules — agents should NOT
    retry internally or swallow their own errors.

EXPECTED OUTPUT per stage (checked by the coordinator)
  collection  -> {"article_ids": [int, ...]}            IDs it stored this run
  security    -> {"approved_ids": [...], "quarantined_ids": [...]}
                 approved_ids must be a subset of the collected IDs
  analysis    -> any dict, e.g. {"processed": 42}       (sentiment/topic/
                                                         classification/stance)
  aggregation -> any dict, e.g. {"aggregated": 42}

OPEN QUESTION FOR THE TEAM: this assumes agents write their own result
rows. If we decide agents should return results for the coordinator to
write instead, only this contract and the coordinator's handling of
analysis outputs change — the sequencing logic stays the same.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Union

from .models import RunContext

Output = Dict[str, Any]
OutputSource = Union[Output, Callable[[RunContext], Output], None]


class Agent(ABC):
    """Base class for pipeline agents. Real agents subclass this."""

    name: str = "agent"

    @abstractmethod
    def run(self, ctx: RunContext) -> Output:
        """Do this stage's work for the run and return a summary dict."""


class StubAgent(Agent):
    """
    Placeholder agent used until the real one is ready.

    output      dict, or a function of the RunContext that returns a dict
    fail_times  fail the first N calls, then succeed (simulates flaky work);
                use -1 to fail on every call
    delay       seconds to sleep before responding (simulates real work)
    """

    def __init__(
        self,
        name: str,
        output: OutputSource = None,
        fail_times: int = 0,
        delay: float = 0.0,
    ) -> None:
        self.name = name
        self._output = output
        self.fail_times = fail_times
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()   # analysis stubs are called from worker threads

    def run(self, ctx: RunContext) -> Output:
        with self._lock:
            self.calls += 1
            call_number = self.calls

        if self.delay:
            time.sleep(self.delay)

        if self.fail_times < 0 or call_number <= self.fail_times:
            raise RuntimeError(f"{self.name} stub: simulated failure on call {call_number}")

        output = self._output(ctx) if callable(self._output) else self._output
        if output is None:
            return {}
        # Copy dicts so callers can't mutate the stub's canned output, but pass
        # anything else through unchanged — checking it is the coordinator's job.
        return dict(output) if isinstance(output, dict) else output


# --- Default stubs: one per stage -----------------------------------------

def stub_collection(article_count: int = 5) -> StubAgent:
    ids = list(range(1, article_count + 1))
    return StubAgent("collection_stub", output={"article_ids": ids})


def stub_security() -> StubAgent:
    # Approves everything that was collected; the real agent will
    # quarantine anything that fails screening.
    return StubAgent(
        "security_stub",
        output=lambda ctx: {"approved_ids": list(ctx.article_ids), "quarantined_ids": []},
    )


def stub_analysis(stage: str) -> StubAgent:
    return StubAgent(f"{stage}_stub", output=lambda ctx: {"processed": len(ctx.approved_ids)})


def stub_aggregation() -> StubAgent:
    return StubAgent(
        "aggregation_stub",
        output=lambda ctx: {
            "aggregated": len(ctx.approved_ids),
            "from_stages": list(ctx.completed_analysis),
        },
    )


def stub_fallback(stage: str) -> StubAgent:
    # Stands in for e.g. a lexicon-based sentiment classifier (VADER).
    return StubAgent(
        f"{stage}_fallback_stub",
        output=lambda ctx: {"processed": len(ctx.approved_ids), "fallback": True},
    )
