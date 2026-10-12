"""
quarantine.py — persists filter rejections to the audit log (S.8).

The filter itself stays pure (text in, result out) so it remains testable
without a database. This module is the only place that writes.


Rewritten 2026-10-10: the previous version opened its own Postgres
connection with psycopg2, which the pipeline does not have. It now goes
through the shared Supabase client (agents/supabase_client.py), the same
path every other agent uses, so the security stage can call it directly.

"""

from __future__ import annotations
 
import logging
from typing import Any, Dict, List, Optional
 
logger = logging.getLogger(__name__)
 
# Excerpt only. A quarantine table holding whole unredacted articles
# becomes its own PII problem.
EXCERPT_CHARS = 400
 
# Must match the CHECK constraints on the table, or the insert is
# rejected with a 400 that reads like a permissions error.
VALID_SOURCES = {"articles", "comments", "reddit_posts", "reddit_comments"}
VALID_REASONS = {
    "prompt_injection_suspected",
    "html_script_detected",
    "exceeds_max_length",
    "empty_or_invalid_type",
}
 
 
def _row(source_table, source_id, reason, flagged_detail, excerpt, run_id):
    if source_table not in VALID_SOURCES:
        raise ValueError(f"source_table must be one of {sorted(VALID_SOURCES)}")
    if reason not in VALID_REASONS:
        # Don't guess - an unknown reason means the filter grew a new
        # rejection path and the table's CHECK constraint needs updating.
        raise ValueError(f"reason {reason!r} is not one of {sorted(VALID_REASONS)}")
    return {
        "source_table": source_table,
        "source_id": str(source_id),
        "run_id": run_id,
        "reason": reason,
        "flagged_detail": flagged_detail,
        "excerpt": (excerpt or "")[:EXCERPT_CHARS] or None,
    }
 
 
def record(source_table: str, source_id: Any, reason: str,
           flagged_detail: Optional[str] = None, excerpt: Optional[str] = None,
           run_id: Optional[int] = None) -> bool:
    """Log one rejection. Returns whether it was written."""
    return record_many([
        _row(source_table, source_id, reason, flagged_detail, excerpt, run_id)
    ])
 
 
def record_many(rows: List[Dict[str, Any]]) -> bool:
    """Log a batch of rejections in one request.
 
    A run that quarantines 40 comments should not make 40 round trips.
    on_conflict matches the table's unique (source_table, source_id,
    run_id), so re-running a stage updates rather than duplicating.
    """
    if not rows:
        return True
 
    try:
        from ..supabase_client import get_client
    except ImportError:  # running as a script rather than inside the package
        from agents.supabase_client import get_client
 
    try:
        get_client().table("quarantined_content").upsert(
            rows, on_conflict="source_table,source_id,run_id"
        ).execute()
        return True
    except Exception as exc:
        # run_pipeline.py uses an in-memory run store, so ctx.run_id may not
        # exist in pipeline_runs and the FK rejects the insert. The rejection
        # itself still needs recording, so retry unlinked.
        if "quarantined_content_run_id_fkey" in str(exc):
            for row in rows:
                row["run_id"] = None
            try:
                get_client().table("quarantined_content").upsert(
                    rows, on_conflict="source_table,source_id,run_id"
                ).execute()
                logger.warning("quarantine: logged %d row(s) without a run link "
                               "(run %s not in pipeline_runs)", len(rows), rows[0].get("run_id"))
                return True
            except Exception as exc2:
                exc = exc2
        logger.error("quarantine logging failed for %d row(s): %s", len(rows), exc)
        return False
 
 
def build_rows(decisions, source_table: str, run_id: Optional[int] = None):
    """Turn (source_id, FilterResult, text) triples into rows to insert.
 
    Lets the security stage collect everything it rejected and write it
    once at the end of the stage, rather than per item.
    """
    rows = []
    for source_id, result, text in decisions:
        if result.passed:
            continue
        rows.append(_row(source_table, source_id, result.reason or "empty_or_invalid_type",
                         result.flagged_pattern, text, run_id))
    return rows
 
 
def unreviewed(limit: int = 50):
    """Rows awaiting human review — the false-positive workflow.
 
    The filter over-blocks on purpose (an article quoting an injection is
    quarantined), so somebody has to be able to look at what it caught.
    """
    try:
        from ..supabase_client import get_client
    except ImportError:
        from agents.supabase_client import get_client
 
    return (
        get_client().table("quarantined_content")
        .select("id, source_table, source_id, reason, flagged_detail, excerpt, quarantined_at")
        .eq("reviewed", False)
        .order("quarantined_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
 