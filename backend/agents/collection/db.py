# db.py
"""Supabase write layer for ClassroomScope articles."""

import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..supabase_client import get_client


def _parse_date(value):
    """Best-effort conversion to ISO 8601. Returns None if unparseable."""
    if not value:
        return None

    # feedparser sometimes gives us a struct_time instead of a string
    if hasattr(value, "tm_year"):
        try:
            return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            return None

    if isinstance(value, str):
        # ISO 8601 (NewsAPI, GNews). Python <3.11 needs the Z swap.
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
        # RFC 822 (RSS feeds)
        try:
            return parsedate_to_datetime(value).isoformat()
        except Exception:
            pass

    return None


def _content_hash(content):
    if not content:
        return None
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _to_row(article):
    """Convert a fetched article dict into a row for the articles table."""
    return {
        "title": article.get("title") or None,
        "author": article.get("author") or None,
        "published_date": _parse_date(article.get("published_date")),
        "source": article.get("source") or None,
        "url": article.get("url"),
        "content": article.get("content") or "",
        "content_hash": _content_hash(article.get("content")),
    }


def insert_articles_returning_ids(articles):
    """Insert articles, skipping any whose url already exists.
    Returns (inserted_ids, skipped_count).

    The ids matter to the pipeline: the coordinator's contract asks the
    collection stage for the IDs it stored this run, and hands them to
    the stages that follow. `ignore_duplicates=True` means the response
    carries only the rows that were actually new, which is exactly that
    set.
    """
    # Drop anything without a url — we can't dedupe or store it.
    rows = [_to_row(a) for a in articles if a.get("url")]
    if not rows:
        return [], 0

    response = (
        get_client()
        .table("articles")
        .upsert(rows, on_conflict="url", ignore_duplicates=True)
        .execute()
    )

    inserted = [r["id"] for r in (response.data or []) if r.get("id") is not None]
    skipped = len(rows) - len(response.data or [])
    return inserted, skipped


def insert_articles(articles):
    """Insert articles, skipping any whose url already exists.
    Returns (inserted_count, skipped_count) — the signature in README 4.2.
    """
    try:
        inserted, skipped = insert_articles_returning_ids(articles)
    except Exception as e:
        # Kept for the standalone scripts, which print and carry on.
        # insert_articles_returning_ids raises instead, because the
        # coordinator needs a failed stage to look like a failure
        # rather than like a run that collected nothing.
        print(f"Insert error: {e}")
        return 0, 0
    return len(inserted), skipped