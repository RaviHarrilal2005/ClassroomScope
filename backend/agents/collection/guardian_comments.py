# guardian_comments.py
"""
Guardian Discussion API comment fetcher.

Fetches comments for Guardian articles that carry a
guardian_discussion_key, normalizes them, and upserts into the
`comments` table. Runs as a separate pass after the article
pipeline has inserted rows into `articles`.

The Discussion API is internal to the Guardian frontend
(discussion.theguardian.com/discussion-api), not part of the
Open Platform. It is undocumented but stable enough for
read-only comment retrieval. Every failure is caught so one bad
article cannot kill the batch.

Verified live, Oct 2026:
  - Route: GET /discussion//p/<shortid>  (double slash; the key
    /p/xxxxx carries its own leading slash).
  - Pagination is over TOP-LEVEL comments. Replies are embedded
    under each top-level comment's `responses` field, so they
    arrive without extra requests.
  - `discussion.commentCount` is the total (incl. replies);
    `discussion.topLevelCommentCount` is the paginated unit.
  - `status` is 'visible' or 'blocked'. Blocked comments are
    moderator-removed; skipped here.
  - `body` is HTML, stripped to plain text before storage.
  - `userProfile.userId` is SHA-256 hashed before storage.

Usage:
    python guardian_comments.py         # all pending articles
    python guardian_comments.py 3       # only 3 articles (test)
"""

import os
import re
import sys
import time
import hashlib
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from db import _supabase

load_dotenv()

BASE_URL = "https://discussion.theguardian.com/discussion-api"
PAGE_SIZE = 100
REQUEST_DELAY = 0.2   # polite; no documented rate limit

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _strip_html(text):
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _hash_author(user_id):
    if not user_id:
        return None
    return hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()


def _comment_to_row(article_id, comment, parent_id):
    return {
        "comment_id": str(comment.get("id")),
        "article_id": article_id,
        "parent_comment_id": parent_id,
        "body_text": _strip_html(comment.get("body")),
        "author_hash": _hash_author(
            (comment.get("userProfile") or {}).get("userId")
        ),
        "created_at": comment.get("isoDateTime"),
        "recommendation_count": comment.get("numRecommends") or 0,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _flatten(article_id, comment, parent_id=None):
    """Return rows for this comment plus all nested replies."""
    rows = []
    if comment.get("status") != "visible":
        # Skipped: moderator-removed, deleted, or otherwise non-visible.
        # Still descend into responses in case any are visible.
        for resp in comment.get("responses") or []:
            rows.extend(_flatten(article_id, resp, parent_id))
        return rows

    cid = str(comment.get("id"))
    rows.append(_comment_to_row(article_id, comment, parent_id))
    for resp in comment.get("responses") or []:
        rows.extend(_flatten(article_id, resp, cid))
    return rows


def fetch_comments_for(article_id, discussion_key):
    """Return a list of normalized rows for one discussion.
    Returns [] on any failure; never raises.
    """
    rows = []
    page = 1
    while True:
        url = f"{BASE_URL}/discussion/{discussion_key}"
        params = {"orderBy": "oldest", "page": page, "pageSize": PAGE_SIZE}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"      page {page} failed: {e}")
            break

        discussion = data.get("discussion") or {}
        comments = discussion.get("comments") or []
        if not comments:
            break

        for c in comments:
            rows.extend(_flatten(article_id, c))

        total_pages = data.get("pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    return rows


def run(limit=None):
    # Articles with comments enabled AND a discussion key.
    query = (
        _supabase.table("articles")
        .select("id, guardian_discussion_key")
        .eq("guardian_commentable", True)
	.eq("llm_relevant", True)
    	.eq("processing_status", "success")
    )
    if limit:
        query = query.limit(limit)
    articles = query.execute().data or []
    articles = [a for a in articles if a.get("guardian_discussion_key")]

    # Skip articles already represented in the comments table.
    existing = (
        _supabase.table("comments")
        .select("article_id")
        .execute()
    ).data or []
    done_ids = {r["article_id"] for r in existing}

    pending = [a for a in articles if a["id"] not in done_ids]
    print(f"Commentable articles:    {len(articles)}")
    print(f"Already have comments:   {len(articles) - len(pending)}")
    print(f"Pending:                 {len(pending)}")

    total_inserted = total_failed = 0
    for i, art in enumerate(pending, 1):
        key = art["guardian_discussion_key"]
        rows = fetch_comments_for(art["id"], key)

        if not rows:
            print(f"  [{i}/{len(pending)}] {key}: 0 comments")
            continue

        # Dedup within batch by comment_id (safety against overlap).
        seen = set()
        unique_rows = []
        for r in rows:
            if r["comment_id"] in seen:
                continue
            seen.add(r["comment_id"])
            unique_rows.append(r)

        try:
            for j in range(0, len(unique_rows), 100):
                batch = unique_rows[j:j + 100]
                _supabase.table("comments").upsert(
                    batch, on_conflict="comment_id"
                ).execute()
            total_inserted += len(unique_rows)
            print(f"  [{i}/{len(pending)}] {key}: {len(unique_rows)} comments")
        except Exception as e:
            print(f"  [{i}/{len(pending)}] {key}: DB error: {e}")
            total_failed += len(unique_rows)

    print(f"\nDone. Inserted: {total_inserted}, Failed: {total_failed}.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)