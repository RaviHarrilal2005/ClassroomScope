"""
Direct Supabase queries: the suite's independent view of the database.

Expected values come from here, never from the code under test. Any query
that can return more than PostgREST's 1,000-row page reads in pages.
"""
from __future__ import annotations

import json
from collections import Counter
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


def corpus_ids(client: Any) -> Set[int]:
    """Every analysable article: LLM-confirmed relevant and downloaded."""
    return {row["id"] for row in page_all(lambda: client.table("articles").select("id")
                                          .eq("llm_relevant", True).eq("processing_status", "success").order("id"))}


def topic_facet(client: Any) -> Dict[str, Any]:
    """
    The /results topic facet, worked out from the raw tables.

    Follows the corpus's documented rule (orchestrator/corpus.py): one topic
    per analysable article, the newest topic_results row; no row, or no
    stable topic ID, means unassigned.
    """
    topics = json.loads(TOPIC_CATALOG.read_text())["topics"]
    corpus = corpus_ids(client)
    newest = {row["article_id"]: row["stable_topic_id"] for row in page_all(
        lambda: client.table("topic_results").select("article_id, stable_topic_id").order("id"))}
    counts = Counter(newest[a] for a in corpus if newest.get(a))
    items = sorted(({"label": topics[topic_id]["label"], "count": n} for topic_id, n in counts.items()),
                   key=lambda item: (-item["count"], item["label"]))
    counted = sum(counts.values())
    return {"counted": counted, "unassigned": len(corpus) - counted, "items": items}


def sentiment_facet(client: Any) -> Dict[str, Any]:
    """
    The /results sentiment share, worked out from the raw tables: one
    sentiment per analysable article, its roberta_news row before any
    other method, then the newest.
    """
    best: Dict[int, Dict[str, Any]] = {}
    for row in page_all(lambda: client.table("sentiment_results")
                        .select("id, article_id, sentiment, method").order("id")):
        current = best.get(row["article_id"])
        if current is None or (row["method"] == "roberta_news") >= (current["method"] == "roberta_news"):
            best[row["article_id"]] = row
    labels = [best[a]["sentiment"] for a in corpus_ids(client) if a in best]
    labels = [label for label in labels if label in ("positive", "neutral", "negative")]
    n = len(labels)
    return {"analysed": n,
            "shares": {s: (labels.count(s) / n if n else 0) for s in ("positive", "neutral", "negative")}}
