"""
Supabase-backed RunStore — writes to pipeline_runs and pipeline_stage_runs.

STATUS: DRAFT, NOT YET RUN AGAINST A REAL DATABASE. The tables it needs
are being added this week (Task 6.3; draft SQL in docs/pipeline_tables.sql).
Its tests get added when we switch to it, along with a check that
the SQL file and the code stay in sync.

To switch app.py over:
    from orchestrator.supabase_store import SupabaseRunStore
    store = SupabaseRunStore.from_env()   # reads SUPABASE_URL / SUPABASE_KEY

Requires `pip install supabase` (see requirements.txt).
"""
from __future__ import annotations

import os
import re
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
    def __init__(self, client: Any) -> None:
        self.client = client

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
        result = self.client.table(RUNS_TABLE).insert(to_row(row)).execute()
        return run_from_row(result.data[0])

    def update_run(self, run_id: int, **fields) -> None:
        check_fields(fields, RUN_FIELDS, RUNS_TABLE)
        self.client.table(RUNS_TABLE).update(to_row(fields)).eq("id", run_id).execute()

    def get_run(self, run_id: int) -> Optional[RunRecord]:
        result = self.client.table(RUNS_TABLE).select("*").eq("id", run_id).limit(1).execute()
        return run_from_row(result.data[0]) if result.data else None

    def list_runs(self, limit: int = 20) -> List[RunRecord]:
        result = self.client.table(RUNS_TABLE).select("*").order("id", desc=True).limit(limit).execute()
        return [run_from_row(r) for r in result.data]

    # --- stages -----------------------------------------------------------
    def create_stage(self, run_id: int, stage_name: str) -> StageRecord:
        row = {"run_id": run_id, "stage_name": stage_name, "status": StageStatus.PENDING, "attempt": 0}
        result = self.client.table(STAGES_TABLE).insert(row).execute()
        return stage_from_row(result.data[0])

    def update_stage(self, stage_id: int, **fields) -> None:
        check_fields(fields, STAGE_FIELDS, STAGES_TABLE)
        self.client.table(STAGES_TABLE).update(to_row(fields)).eq("id", stage_id).execute()

    def list_stages(self, run_id: int) -> List[StageRecord]:
        result = self.client.table(STAGES_TABLE).select("*").eq("run_id", run_id).order("id").execute()
        return [stage_from_row(r) for r in result.data]
