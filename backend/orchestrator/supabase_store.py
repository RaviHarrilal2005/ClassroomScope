"""
Supabase-backed RunStore — writes to pipeline_runs and pipeline_stage_runs.

STATUS: in use. app.py selects this store when SUPABASE_URL and
SUPABASE_KEY are set (see build_run_store there). Every method has been
run against the real database.

The deployed schema still differs from docs/pipeline_tables.sql in a few
places (attempt defaults, unique key, articles_collected default); the
full list is in docs/pipeline-coordinator.md.

Every method takes a lock -- see the class docstring below.

Its tests are still to be written, along with a check that the deployed
schema and the code stay in sync.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import RunRecord, StageRecord, utcnow
from .stages import RunStatus, StageStatus
from .store import RUN_FIELDS, STAGE_FIELDS, RunStore, check_fields

RUNS_TABLE = "pipeline_runs"
STAGES_TABLE = "pipeline_stage_runs"
_FRACTION = re.compile(r"^(.*T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$")


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse a timestamp from Supabase. Works on Python 3.9+, which is
    stricter than 3.11 about 'Z' suffixes and fractional-second digits."""
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).replace(" ", "T", 1).replace("Z", "+00:00")
    match = _FRACTION.match(text)
    if match:
        base, fraction, rest = match.groups()
        fraction = "." + (fraction[1:] + "000000")[:6] if fraction else ""
        text = base + fraction + rest
    return datetime.fromisoformat(text)


def to_row(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Python values -> JSON values for the Supabase client."""
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in fields.items()}


def first_row(result: Any, table: str) -> Dict[str, Any]:
    """
    The row an insert returned.

    Empty data means PostgREST accepted the insert but returned nothing,
    which normally means the key may INSERT but not SELECT. Raising here
    gives that message instead of an IndexError further down.
    """
    data = getattr(result, "data", None)
    if not data:
        raise RuntimeError(
            f"{table}: insert returned no row. Check that SUPABASE_KEY has INSERT "
            f"and SELECT on {table} — a service-role key bypasses RLS."
        )
    return data[0]


def run_from_row(row: Dict[str, Any]) -> RunRecord:
    return RunRecord(
        id=row["id"],
        trigger_type=row["trigger_type"],
        status=row["status"],
        started_at=parse_ts(row["started_at"]),
        finished_at=parse_ts(row.get("finished_at")),
        articles_collected=row.get("articles_collected"),
        notes=row.get("notes"),
    )


def stage_from_row(row: Dict[str, Any]) -> StageRecord:
    return StageRecord(
        id=row["id"],
        run_id=row["run_id"],
        stage_name=row["stage_name"],
        status=row["status"],
        attempt=row.get("attempt") or 0,
        error_detail=row.get("error_detail"),
        started_at=parse_ts(row.get("started_at")),
        finished_at=parse_ts(row.get("finished_at")),
    )


class SupabaseRunStore(RunStore):
    """
    Thread-safe, like InMemoryRunStore: the four analysis stages update
    their rows concurrently (coordinator.py runs them in a thread pool)
    and the supabase-py client underneath is one HTTP connection that
    cannot be shared across threads. Without this lock the parallel
    stages fail with 'ReadError: [WinError 10035]' or a similar
    transport error. The calls are short status writes, so serialising
    them costs nothing next to the agents' own work.
    """

    def __init__(self, client: Any) -> None:
        self.client = client
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "SupabaseRunStore":
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY to use SupabaseRunStore")
        try:
            from supabase import create_client  # imported here so the app runs without it
        except ImportError as exc:
            raise RuntimeError("SupabaseRunStore needs the client library: pip install supabase") from exc
        return cls(create_client(url, key))

    # --- runs -------------------------------------------------------------
    def create_run(self, trigger_type: str) -> RunRecord:
        row = {"trigger_type": trigger_type, "status": RunStatus.RUNNING, "started_at": utcnow()}
        with self._lock:
            result = self.client.table(RUNS_TABLE).insert(to_row(row)).execute()
        return run_from_row(first_row(result, RUNS_TABLE))

    def update_run(self, run_id: int, **fields) -> None:
        check_fields(fields, RUN_FIELDS, RUNS_TABLE)
        with self._lock:
            self.client.table(RUNS_TABLE).update(to_row(fields)).eq("id", run_id).execute()

    def get_run(self, run_id: int) -> Optional[RunRecord]:
        with self._lock:
            result = self.client.table(RUNS_TABLE).select("*").eq("id", run_id).limit(1).execute()
        return run_from_row(result.data[0]) if result.data else None

    def list_runs(self, limit: int = 20) -> List[RunRecord]:
        with self._lock:
            result = self.client.table(RUNS_TABLE).select("*").order("id", desc=True).limit(limit).execute()
        return [run_from_row(r) for r in result.data]

    # --- stages -----------------------------------------------------------
    def create_stage(self, run_id: int, stage_name: str) -> StageRecord:
        # attempt is left to the column default: the deployed table checks
        # attempt >= 1, so an explicit 0 placeholder is rejected. The
        # coordinator sets the real 1-based number when the stage runs.
        row = {"run_id": run_id, "stage_name": stage_name, "status": StageStatus.PENDING}
        with self._lock:
            result = self.client.table(STAGES_TABLE).insert(to_row(row)).execute()
        return stage_from_row(first_row(result, STAGES_TABLE))

    def update_stage(self, stage_id: int, **fields) -> None:
        check_fields(fields, STAGE_FIELDS, STAGES_TABLE)
        with self._lock:
            self.client.table(STAGES_TABLE).update(to_row(fields)).eq("id", stage_id).execute()

    def list_stages(self, run_id: int) -> List[StageRecord]:
        with self._lock:
            result = self.client.table(STAGES_TABLE).select("*").eq("run_id", run_id).order("id").execute()
        return [stage_from_row(r) for r in result.data]
