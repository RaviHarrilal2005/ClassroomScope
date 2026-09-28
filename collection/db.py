# db.py
"""Supabase write layer for ClassroomScope articles."""

import os
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY"),
)


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


def insert_articles(articles):
    """Insert articles, skipping any whose url already exists.
    Returns (inserted_count, skipped_count).
    """
    # Drop anything without a url — we can't dedupe or store it.
    rows = [_to_row(a) for a in articles if a.get("url")]
    if not rows:
        return 0, 0

    try:
        response = (
            _supabase.table("articles")
            .upsert(rows, on_conflict="url", ignore_duplicates=True)
            .execute()
        )
    except Exception as e:
        print(f"Insert error: {e}")
        return 0, 0

    inserted = len(response.data) if response.data else 0
    skipped = len(rows) - inserted
    return inserted, skipped