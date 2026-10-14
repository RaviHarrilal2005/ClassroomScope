"""
The dashboard's top_topics facet: articles per topic, in the shape the
aggregation plan (docs/superpowers/plans/2026-09-29-aggregation-agent.md)
will snapshot. Until that agent exists, orchestrator/corpus.py counts
the filtered articles with top_topics() on each request.

Unassigned articles are reported, not dropped: more than half of the
analysed articles fit no topic, and a chart of only the assigned ones
would hide that.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

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
