"""
The analysable corpus for the dashboard: each article with one source
type, stakeholder, topic and sentiment, filtered and searched per request.

MVP (README, "MVP features — come back to these"): each corpus refresh
reads four tables (articles, classification_results, topic_results,
sentiment_results) and filters in Python, behind a 60-second cache; a search also reads
`comments`. Fine at a few
hundred articles. The aggregation snapshot, or a Postgres view, should
replace it once the corpus grows or the numbers must match a run.

Merge rules, one value per article:
  * classification: any classifier beats `baseline_keyword`; ties go to
    the newest `classified_at`.
  * topic: the newest topic_results row. No row, or no stable topic ID,
    means unassigned.
  * sentiment: `roberta_news` beats any other method; ties go to the
    newest row. No row means no sentiment (None).
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
PREFERRED_SENTIMENT_METHOD = "roberta_news"
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


def _method_rank(row: Mapping[str, Any]) -> int:
    return 1 if row.get("method") == PREFERRED_SENTIMENT_METHOD else 0


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
    sentiment_rows = page_all(lambda: client.table("sentiment_results")
                              .select("id, article_id, sentiment, method").order("id"))

    best: Dict[Any, Mapping[str, Any]] = {}
    for row in classifications:
        current = best.get(row["article_id"])
        if current is None or _classifier_rank(row) > _classifier_rank(current):
            best[row["article_id"]] = row
    newest_topic = {row["article_id"]: row for row in topic_rows}  # ordered by id, so the last wins
    # Ordered by id, so a later row of the same preference replaces an earlier one.
    sentiment: Dict[Any, Mapping[str, Any]] = {}
    for row in sentiment_rows:
        current = sentiment.get(row["article_id"])
        if current is None or _method_rank(row) >= _method_rank(current):
            sentiment[row["article_id"]] = row

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
            "sentiment": sentiment.get(article["id"], {}).get("sentiment"),
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


# --- filtering -------------------------------------------------------------

def parse_filters(args: Mapping[str, Any]) -> Dict[str, str]:
    """The filter query params, trimmed and checked. Raises ValueError with a message for the caller."""
    filters = {key: (args.get(key) or "").strip() for key in FILTER_KEYS}
    for key in ("from", "to"):
        if filters[key]:
            try:
                filters[key] = datetime.strptime(filters[key], "%Y-%m-%d").date().isoformat()
            except ValueError:
                raise ValueError(f"'{key}' must be a date like 2026-10-08.") from None
    if filters["from"] and filters["to"] and filters["from"] > filters["to"]:
        raise ValueError("'from' must not be after 'to'.")
    if filters["q"] and not 2 <= len(filters["q"]) <= 100:
        raise ValueError("Search terms must be 2 to 100 characters.")
    return filters


def make_snippet(text: str, q: str, context: int = SNIPPET_CONTEXT) -> Optional[str]:
    """About `context` characters either side of the first case-insensitive match of `q`, or None."""
    at = text.lower().find(q.lower())
    if at < 0:
        return None
    start, end = max(0, at - context), min(len(text), at + len(q) + context)
    body = " ".join(text[start:end].split())
    return ("…" if start > 0 else "") + body + ("…" if end < len(text) else "")


def _day(value: Optional[str]) -> Optional[str]:
    """The YYYY-MM-DD part of an ISO timestamp."""
    return value[:10] if value else None


def filter_articles(articles: Iterable[Article], filters: Mapping[str, str]) -> List[Article]:
    """
    The articles matching every set filter, newest first, undated last.

    `q` matches the title or the text, ignoring case. Each article comes
    back with a `snippet` from its text around the match: None when there
    is no `q`, or when only the title matched.
    """
    start, end, q = filters.get("from"), filters.get("to"), filters.get("q")
    matched = []
    for article in articles:
        if start or end:
            day = _day(article.get("published_date"))
            if day is None or (start and day < start) or (end and day > end):
                continue
        if any(filters.get(key) and article.get(field) != filters[key]
               for key, field in EXACT_FILTERS.items()):
            continue
        snippet = None
        if q:
            snippet = make_snippet(article.get("clean_content") or "", q)
            if snippet is None and q.lower() not in (article.get("title") or "").lower():
                continue
        matched.append({**article, "snippet": snippet})
    matched.sort(key=lambda a: a.get("published_date") or "", reverse=True)
    return matched


def filter_options(articles: List[Article]) -> Dict[str, Any]:
    """What the filter controls offer. Built from the whole corpus, so options don't vanish while filtering."""
    days = sorted(day for day in (_day(a.get("published_date")) for a in articles) if day)
    topics = {a["stable_topic_id"]: a["topic"] for a in articles if a.get("stable_topic_id")}
    return {
        "source_types": sorted({a["source_type"] for a in articles if a.get("source_type")}),
        "stakeholders": sorted({a["stakeholder"] for a in articles if a.get("stakeholder")}),
        "topics": sorted(({"id": i, "label": label} for i, label in topics.items()),
                         key=lambda t: t["label"]),
        "date_min": days[0] if days else None,
        "date_max": days[-1] if days else None,
    }


def results_payload(corpus: Corpus, filters: Mapping[str, str]) -> Dict[str, Any]:
    """The corpus-backed part of /results: top_topics, articles and filter_options."""
    if not corpus["available"]:
        return {
            "top_topics": topics_unavailable(corpus["reason"]),
            "articles": {"available": False, "reason": corpus["reason"], "total": 0, "corpus": 0, "items": []},
            "filter_options": filter_options([]),
        }
    everything = corpus["articles"]
    matched = filter_articles(everything, filters)
    if matched:
        topics = top_topics(matched)
    elif any(filters.values()):
        topics = topics_unavailable("No articles match these filters.")
    else:
        topics = topics_unavailable("There are no analysable articles yet.")
    return {
        "top_topics": topics,
        "articles": {
            "available": True,
            "reason": None,
            "total": len(matched),
            "corpus": len(everything),
            "items": [{field: article.get(field) for field in ARTICLE_FIELDS} for article in matched],
        },
        "filter_options": filter_options(everything),
    }


# --- comment search --------------------------------------------------------

def comments_unavailable(reason: str) -> Dict[str, Any]:
    return {"available": False, "reason": reason, "total": 0, "comments": []}


def escape_like(text: str) -> str:
    """`text` for a LIKE pattern, with its wildcards matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_comments(client: Any, articles: List[Article], q: str,
                    limit: int = COMMENT_LIMIT) -> Dict[str, Any]:
    """
    Comments on `articles` containing `q`, ignoring case, newest first.

    `total` counts every match; at most `limit` come back. PostgREST reads
    `*` in a pattern as a wildcard and has no escape for it, so a `*` in
    `q` matches anything.
    """
    if not articles:
        return {"available": True, "reason": None, "total": 0, "comments": []}
    titles = {a["id"]: a.get("title") for a in articles}
    # ponytail: the article IDs travel in the URL; past ~1,500 articles move this into an RPC.
    response = (client.table("comments")
                .select("comment_id, article_id, body_text, created_at, recommendation_count", count="exact")
                .in_("article_id", sorted(titles))
                .ilike("body_text", f"%{escape_like(q)}%")
                .order("created_at", desc=True)
                .limit(limit)
                .execute())
    return {
        "available": True,
        "reason": None,
        "total": response.count or 0,
        "comments": [{
            "comment_id": c["comment_id"],
            "article_id": c["article_id"],
            "article_title": titles.get(c["article_id"]),
            "created_at": c.get("created_at"),
            "recommendation_count": c.get("recommendation_count"),
            "snippet": make_snippet(c.get("body_text") or "", q),
        } for c in response.data],
    }


def from_env() -> Tuple[Callable[[], Corpus], CommentSearch]:
    """The corpus reader and comment search for this environment's Supabase, or unavailable stand-ins."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return (lambda: unavailable(NOT_CONFIGURED)), (lambda articles, q: comments_unavailable(NOT_CONFIGURED))
    from supabase import create_client  # imported here so the app runs without it

    client = create_client(url, key)
    return reader(client), (lambda articles, q: search_comments(client, articles, q))
