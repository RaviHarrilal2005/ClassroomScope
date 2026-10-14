"""
Direct Supabase queries: the suite's independent view of the database.

Expected values come from here, never from the code under test. Any query
that can return more than PostgREST's 1,000-row page reads in pages.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Set, Tuple

from e2e.settings import TOPIC_CATALOG

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


def run_row(client: Any, run_id: int) -> Dict[str, Any]:
    return client.table("pipeline_runs").select("*").eq("id", run_id).execute().data[0]


def stage_rows(client: Any, run_id: int) -> List[Dict[str, Any]]:
    return (client.table("pipeline_stage_runs").select("stage_name, status, error_detail")
            .eq("run_id", run_id).order("id").execute().data)


def classified_between(client: Any, start_iso: str, end_iso: str) -> Set[int]:
    """Articles whose classification rows were written in this window."""
    rows = page_all(lambda: client.table("classification_results").select("article_id")
                    .gte("classified_at", start_iso).lte("classified_at", end_iso).order("id"))
    return {row["article_id"] for row in rows}


def analysable(client: Any, ids: Set[int]) -> Set[int]:
    """The articles among `ids` that analysis can use: LLM-confirmed relevant and downloaded."""
    if not ids:
        return set()
    rows = (client.table("articles").select("id").in_("id", sorted(ids))
            .eq("llm_relevant", True).eq("processing_status", "success").execute().data)
    return {row["id"] for row in rows}


def articles_with_rows(client: Any, table: str, ids: Set[int]) -> Set[int]:
    """The articles among `ids` that have at least one row in `table`."""
    if not ids:
        return set()
    rows = client.table(table).select("article_id").in_("article_id", sorted(ids)).execute().data
    return {row["article_id"] for row in rows}


def topic_facet(client: Any) -> Dict[str, Any]:
    """The /results topic facet as Supabase's own exact counts give it."""
    topics = json.loads(TOPIC_CATALOG.read_text())["topics"]

    def exact(query: Any) -> int:
        return query.limit(1).execute().count or 0

    counts = {topic_id: exact(client.table("topic_results").select("id", count="exact")
                              .eq("stable_topic_id", topic_id))
              for topic_id in topics}
    items = sorted(({"label": topics[t]["label"], "count": n} for t, n in counts.items() if n),
                   key=lambda item: (-item["count"], item["label"]))
    unassigned = exact(client.table("topic_results").select("id", count="exact").is_("stable_topic_id", "null"))
    return {"counted": sum(counts.values()), "unassigned": unassigned, "items": items}
