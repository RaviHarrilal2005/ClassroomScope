"""
Topic counts for the dashboard, read straight from topic_results.

A stand-in until the aggregation agent exists. The aggregation plan
(docs/superpowers/plans/2026-09-29-aggregation-agent.md) computes this
same facet into a snapshot, in this shape, so the dashboard keeps
working when it lands; until then /results counts the table live.

Unassigned articles are reported, not dropped: more than half of the
analysed articles fit no topic, and a chart of only the assigned ones
would hide that.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Iterable, List

logger = logging.getLogger(__name__)

Facet = Dict[str, Any]


def unavailable(reason: str) -> Facet:
    return {"available": False, "reason": reason, "counted": 0, "unassigned": 0, "items": []}


def top_topics(rows: Iterable[Dict[str, Any]]) -> Facet:
    """Articles per topic, most frequent first. A row with no stable topic ID is unassigned."""
    counts: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    unassigned = 0
    for row in rows:
        topic_id = row.get("stable_topic_id")
        if not topic_id:
            unassigned += 1
            continue
        counts[topic_id] = counts.get(topic_id, 0) + 1
        labels.setdefault(topic_id, row.get("topic") or topic_id)

    if not counts:
        if unassigned:
            return unavailable(f"None of the {unassigned} analysed articles has a topic yet.")
        return unavailable("topic_results has no rows yet.")

    items = sorted(
        ({"label": labels[t], "count": n} for t, n in counts.items()),
        key=lambda item: (-item["count"], item["label"]),
    )
    return {
        "available": True,
        "reason": None,
        "counted": sum(counts.values()),
        "unassigned": unassigned,
        "items": items,
    }


def read_topic_rows(client: Any, page_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Every row of topic_results.

    PostgREST returns at most its max-rows per request whatever range is
    asked for, so this pages until a page comes back empty rather than
    trusting a short page to be the last.
    """
    rows: List[Dict[str, Any]] = []
    while True:
        page = (
            client.table("topic_results")
            .select("stable_topic_id, topic")
            .order("id")
            .range(len(rows), len(rows) + page_size - 1)
            .execute()
            .data
        )
        if not page:
            return rows
        rows.extend(page)


def reader(client: Any) -> Callable[[], Facet]:
    """
    The top_topics facet, recounted on each call.

    A failed read becomes an unavailable facet rather than a 500: the
    rest of the dashboard should still load, and the reason says why
    the topics are missing.
    """
    def read() -> Facet:
        try:
            return top_topics(read_topic_rows(client))
        except Exception:
            logger.exception("Could not read topic_results")
            return unavailable("Could not read topic_results; see the backend log.")

    return read


def reader_from_env() -> Callable[[], Facet]:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return lambda: unavailable("Supabase is not configured, so there are no topic results to read.")
    from supabase import create_client  # imported here so the app runs without it

    return reader(create_client(url, key))
