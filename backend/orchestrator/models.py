"""
Data passed around by the coordinator.

RunRecord and StageRecord mirror the two tables proposed in Task 6.3
(pipeline_runs and pipeline_stage_runs) column for column, so moving
from the in-memory store to Supabase is a storage swap, not a redesign.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RunContext:
    """
    What the coordinator hands to each agent.

    Deliberately contains IDs, never article text: agents read the
    articles they need from the database and write their own results
    back to it. The coordinator only moves control information.
    """

    run_id: int
    article_ids: List[int] = field(default_factory=list)          # set after collection
    approved_ids: List[int] = field(default_factory=list)         # set after security
    completed_analysis: List[str] = field(default_factory=list)   # set before aggregation


@dataclass
class RunRecord:
    """One row of pipeline_runs."""

    id: int
    trigger_type: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    articles_collected: Optional[int] = None
    notes: Optional[str] = None


@dataclass
class StageRecord:
    """One row of pipeline_stage_runs."""

    id: int
    run_id: int
    stage_name: str
    status: str
    attempt: int = 0
    error_detail: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


def to_dict(record: Any) -> Dict[str, Any]:
    """Dataclass -> JSON-safe dict (datetimes become ISO strings)."""
    data = asdict(record)
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data
