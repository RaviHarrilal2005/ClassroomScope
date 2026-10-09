"""
Direct Supabase queries: the suite's independent view of the database.

Expected values come from here, never from the code under test. Any query
that can return more than PostgREST's 1,000-row page reads in pages.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

# The tables a run writes to, for the before/after footprint.
FOOTPRINT_TABLES = ("pipeline_runs", "pipeline_stage_runs", "articles",
                    "classification_results", "topic_results")


def page_all(make_query: Callable[[], Any], size: int = 1000) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    while True:
        page = make_query().range(len(rows), len(rows) + size - 1).execute().data
        if not page:
            return rows
        rows.extend(page)


def max_id(client: Any, table: str) -> int:
    rows = client.table(table).select("id").order("id", desc=True).limit(1).execute().data
    return rows[0]["id"] if rows else 0


def row_count(client: Any, table: str) -> int:
    return client.table(table).select("id", count="exact").limit(1).execute().count or 0


def snapshot(client: Any) -> Dict[str, Tuple[int, int]]:
    """(row count, highest id) for each table a run writes to."""
    return {table: (row_count(client, table), max_id(client, table)) for table in FOOTPRINT_TABLES}


def ids_above(client: Any, table: str, after_id: int) -> List[int]:
    rows = page_all(lambda: client.table(table).select("id").gt("id", after_id).order("id"))
    return [row["id"] for row in rows]


def count_since(client: Any, table: str, column: str, since_iso: str) -> int:
    return client.table(table).select("id", count="exact").gte(column, since_iso).limit(1).execute().count or 0
