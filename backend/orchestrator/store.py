"""
Where run and stage status gets recorded.

RunStore is the interface the coordinator talks to. Two implementations:

  InMemoryRunStore  — works today, no database needed. Data is lost when
                      the server restarts. Used for development and tests.
  SupabaseRunStore  — (supabase_store.py) writes to pipeline_runs and
                      pipeline_stage_runs once those tables exist.

The coordinator only ever calls the methods below, so switching stores
is a one-line change in app.py.
"""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Dict, List, Optional

from .models import RunRecord, StageRecord, utcnow
from .stages import RunStatus, StageStatus

# Fields the coordinator is allowed to update — keeps typos from silently
# creating new attributes instead of updating real columns.
RUN_FIELDS = {"status", "finished_at", "articles_collected", "notes"}
STAGE_FIELDS = {"status", "attempt", "error_detail", "started_at", "finished_at"}


class RunStore(ABC):
    @abstractmethod
    def create_run(self, trigger_type: str) -> RunRecord: ...

    @abstractmethod
    def update_run(self, run_id: int, **fields) -> None: ...

    @abstractmethod
    def get_run(self, run_id: int) -> Optional[RunRecord]: ...

    @abstractmethod
    def list_runs(self, limit: int = 20) -> List[RunRecord]: ...

    @abstractmethod
    def create_stage(self, run_id: int, stage_name: str) -> StageRecord: ...

    @abstractmethod
    def update_stage(self, stage_id: int, **fields) -> None: ...

    @abstractmethod
    def list_stages(self, run_id: int) -> List[StageRecord]: ...


def check_fields(fields: dict, allowed: set, table: str) -> None:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unknown {table} column(s): {', '.join(sorted(unknown))}")


class InMemoryRunStore(RunStore):
    """Thread-safe: the four analysis stages update their rows concurrently."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[int, RunRecord] = {}
        self._stages: Dict[int, StageRecord] = {}
        self._next_run_id = 1
        self._next_stage_id = 1

    def create_run(self, trigger_type: str) -> RunRecord:
        with self._lock:
            run = RunRecord(
                id=self._next_run_id,
                trigger_type=trigger_type,
                status=RunStatus.RUNNING,
                started_at=utcnow(),
            )
            self._runs[run.id] = run
            self._next_run_id += 1
            return replace(run)

    def update_run(self, run_id: int, **fields) -> None:
        check_fields(fields, RUN_FIELDS, "pipeline_runs")
        with self._lock:
            run = self._runs[run_id]
            self._runs[run_id] = replace(run, **fields)

    def get_run(self, run_id: int) -> Optional[RunRecord]:
        with self._lock:
            run = self._runs.get(run_id)
            return replace(run) if run else None

    def list_runs(self, limit: int = 20) -> List[RunRecord]:
        with self._lock:
            newest_first = sorted(self._runs.values(), key=lambda r: r.id, reverse=True)
            return [replace(r) for r in newest_first[:limit]]

    def create_stage(self, run_id: int, stage_name: str) -> StageRecord:
        with self._lock:
            stage = StageRecord(
                id=self._next_stage_id,
                run_id=run_id,
                stage_name=stage_name,
                status=StageStatus.PENDING,
            )
            self._stages[stage.id] = stage
            self._next_stage_id += 1
            return replace(stage)

    def update_stage(self, stage_id: int, **fields) -> None:
        check_fields(fields, STAGE_FIELDS, "pipeline_stage_runs")
        with self._lock:
            stage = self._stages[stage_id]
            self._stages[stage_id] = replace(stage, **fields)

    def list_stages(self, run_id: int) -> List[StageRecord]:
        with self._lock:
            rows = [s for s in self._stages.values() if s.run_id == run_id]
            return [replace(s) for s in sorted(rows, key=lambda s: s.id)]
