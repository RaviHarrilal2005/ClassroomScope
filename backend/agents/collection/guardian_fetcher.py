# guardian_fetcher.py
"""
Guardian Open Platform article fetcher.

Fetches Guardian articles about generative AI in education, normalized
into the flat article shape used by db.insert_articles().

Also derives the Discussion API path segment from each article's
short URL. Example: https://www.theguardian.com/p/x5m583 -> /p/x5m583.

Verified against live Guardian API:
  - `shortUrl` is populated whenever the article has one.
  - `commentable` is present in `fields` only when true; absence -> False.
  - `tag=education/education` + the AI query below returns ~428 articles
    across sections (Education, Opinion, Letters, Technology), all
    education-relevant. This is the tag filter, not `section`, so
    cross-section coverage is included by design.
  - `order-by=newest` is deliberate: under `relevance` the same top
    articles return every run and dedup skips them, so a scheduled
    collection would never see new items.

Usage (from backend/):
    python -m agents.collection.guardian_fetcher        # up to MAX_PAGES
    python -m agents.collection.guardian_fetcher 2      # 2 pages
"""

import re
import sys
import time

import requests

from ..config import optional_key

BASE_URL = "https://content.guardianapis.com/search"
QUERY = (
    '"generative AI" OR "gen AI" OR "large language model" OR '
    'ChatGPT OR Gemini OR Claude OR Copilot'
)
TAG = "education/education"
FIELDS = "shortUrl,commentable,byline,trailText"

PAGE_SIZE = 50
MAX_PAGES = 10        # ~500 articles max per run
REQUEST_DELAY = 1.2   # Developer tier ~1 req/sec

_DISCUSSION_KEY_RE = re.compile(r"/p/([A-Za-z0-9]+)\s*$")


def _derive_discussion_key(short_url):
    """'https://www.theguardian.com/p/x5m583' -> '/p/x5m583'. None if absent."""
    if not short_url:
        return None
    m = _DISCUSSION_KEY_RE.search(short_url)
    return f"/p/{m.group(1)}" if m else None


def _to_article(item):
    fields = item.get("fields") or {}
    return {
        "title": item.get("webTitle"),
        "author": fields.get("byline") or None,
        "published_date": item.get("webPublicationDate"),
        "source": "The Guardian",
        "url": item.get("webUrl"),
        "content": fields.get("trailText") or "",
        "guardian_discussion_key": _derive_discussion_key(fields.get("shortUrl")),
        "guardian_commentable": "commentable" in fields,
    }


def fetch_from_guardian(max_pages=MAX_PAGES, page_size=PAGE_SIZE):
    """Fetch Guardian articles about generative AI in education.

    Returns a flat list of article dicts compatible with
    db.insert_articles(). Partial results on error; never raises.
    """
    # Read when fetching, not at import, like the other fetchers: the
    # app imports this module before backend/.env may be loaded.
    api_key = optional_key("GUARDIAN_API_KEY")
    if not api_key:
        print("GUARDIAN_API_KEY not set in .env")
        return []

    articles = []
    for page in range(1, max_pages + 1):
        params = {
            "api-key": api_key,
            "q": QUERY,
            "tag": TAG,
            "lang": "en",
            "page-size": page_size,
            "page": page,
            "show-fields": FIELDS,
            "order-by": "newest",
        }
        try:
            r = requests.get(BASE_URL, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"Guardian error on page {page}: {e}")
            break

        response = data.get("response") or {}
        results = response.get("results") or []
        for item in results:
            articles.append(_to_article(item))

        total_pages = response.get("pages", 1)
        print(f"  page {page}/{min(max_pages, total_pages)}: {len(results)} results")

        if page >= total_pages:
            break
        time.sleep(REQUEST_DELAY)

    return articles


if __name__ == "__main__":
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else MAX_PAGES
    arts = fetch_from_guardian(max_pages=pages)
    print(f"\nFetched {len(arts)} Guardian articles total.")

    commentable = [a for a in arts if a["guardian_commentable"]]
    with_key = [a for a in arts if a["guardian_discussion_key"]]
    print(f"  commentable:         {len(commentable)}")
    print(f"  with discussion key: {len(with_key)}")

    for a in arts[:5]:
        print("---")
        print("  title:          ", a["title"])
        print("  discussion_key: ", a["guardian_discussion_key"])
        print("  commentable:    ", a["guardian_commentable"])