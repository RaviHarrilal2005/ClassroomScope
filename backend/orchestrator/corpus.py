"""
The analysable corpus for the dashboard: each article with one source
type, stakeholder and topic, filtered and searched per request.

MVP (README, "MVP features — come back to these"): this reads four
tables and filters in Python, behind a 60-second cache. Fine at a few
hundred articles. The aggregation snapshot, or a Postgres view, should
replace it once the corpus grows or the numbers must match a run.

Merge rules, one value per article:
  * classification: any classifier beats `baseline_keyword`; ties go to
    the newest `classified_at`.
  * topic: the newest topic_results row. No row, or no stable topic ID,
    means unassigned.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .topic_counts import top_topics
from .topic_counts import unavailable as topics_unavailable

logger = logging.getLogger(__name__)

Article = Dict[str, Any]
Corpus = Dict[str, Any]  # {"available": bool, "reason": str | None, "articles": [Article]}
CommentSearch = Callable[[List[Article], str], Dict[str, Any]]

FILTER_KEYS = ("from", "to", "source_type", "stakeholder", "topic", "q")
# Exact-match filters: query param -> article field.
EXACT_FILTERS = {"source_type": "source_type", "stakeholder": "stakeholder", "topic": "stable_topic_id"}
# What /results sends per article. clean_content stays on the server.
ARTICLE_FIELDS = ("id", "title", "url", "source", "published_date", "source_type",
                  "stakeholder", "stable_topic_id", "topic", "snippet")
BASELINE_CLASSIFIER = "baseline_keyword"
SNIPPET_CONTEXT = 80
CACHE_SECONDS = 60
COMMENT_LIMIT = 50
NOT_CONFIGURED = "Supabase is not configured, so there are no articles to read."


# --- reading ---------------------------------------------------------------

def page_all(query: Callable[[], Any], page_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Every row a query matches. `query` builds a fresh query on each call.

    PostgREST returns at most its max-rows per request whatever range is
    asked for, so this pages until a page comes back empty rather than
    trusting a short page to be the last.
    """
    rows: List[Dict[str, Any]] = []
    while True:
        page = query().range(len(rows), len(rows) + page_size - 1).execute().data
        if not page:
            return rows
        rows.extend(page)


def _classifier_rank(row: Mapping[str, Any]) -> Tuple[bool, str]:
    return (row.get("classifier") != BASELINE_CLASSIFIER, row.get("classified_at") or "")


def read_corpus(client: Any) -> List[Article]:
    """The analysable articles, each with source_type, stakeholder, stable_topic_id and topic."""
    articles = page_all(lambda: client.table("articles")
                        .select("id, title, source, url, published_date, clean_content")
                        .eq("llm_relevant", True).eq("processing_status", "success").order("id"))
    classifications = page_all(lambda: client.table("classification_results")
                               .select("article_id, classifier, stakeholder_category, source_type, classified_at")
                               .order("id"))
    topic_rows = page_all(lambda: client.table("topic_results")
                          .select("article_id, stable_topic_id, topic").order("id"))

    best: Dict[Any, Mapping[str, Any]] = {}
    for row in classifications:
        current = best.get(row["article_id"])
        if current is None or _classifier_rank(row) > _classifier_rank(current):
            best[row["article_id"]] = row
    newest_topic = {row["article_id"]: row for row in topic_rows}  # ordered by id, so the last wins

    corpus = []
    for article in articles:
        label = best.get(article["id"], {})
        topic = newest_topic.get(article["id"], {})
        topic_id = topic.get("stable_topic_id")
        corpus.append({
            **article,
            "clean_content": article.get("clean_content") or "",
            "source_type": label.get("source_type"),
            "stakeholder": label.get("stakeholder_category"),
            "stable_topic_id": topic_id,
            "topic": (topic.get("topic") or topic_id) if topic_id else None,
        })
    return corpus


def unavailable(reason: str) -> Corpus:
    return {"available": False, "reason": reason, "articles": []}


def reader(client: Any, ttl: float = CACHE_SECONDS,
           clock: Callable[[], float] = time.monotonic) -> Callable[[], Corpus]:
    """
    The corpus, re-read at most every `ttl` seconds.

    A failed read becomes an unavailable corpus rather than a 500, and is
    not cached, so the next request tries again.
    """
    # ponytail: one cache per process and no lock; two requests at expiry may both re-read.
    cache: Dict[str, Any] = {"at": None, "corpus": None}

    def read() -> Corpus:
        if cache["at"] is not None and clock() - cache["at"] < ttl:
            return cache["corpus"]
        try:
            corpus = {"available": True, "reason": None, "articles": read_corpus(client)}
        except Exception:
            logger.exception("Could not read the article corpus")
            return unavailable("Could not read the articles; see the backend log.")
        cache.update(at=clock(), corpus=corpus)
        return corpus

    return read
