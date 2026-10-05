# preprocess.py
"""Fetch each relevant article's URL, extract body text, store clean_content.
Usage:
    python preprocess.py          # process all pending
    python preprocess.py 5        # process 5 rows (test run)
"""

import sys
import time
import re
import html as html_lib
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from ..supabase_client import get_client

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def extract_body(soup):
    """Strip navigation/scripts/ads, return paragraph text."""
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "noscript"]):
        tag.decompose()

    article = soup.find("article")
    container = article if article else soup

    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if len(p) > 40]

    if not paragraphs:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 40]

    return "\n\n".join(paragraphs)


def clean_text(text):
    """Normalize whitespace and unescape entities."""
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_and_extract(url):
    """Returns (clean_content, status, note)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException as e:
        return None, "failed", f"request error: {e}"

    if r.status_code == 403:
        return None, "paywalled", "403 forbidden"
    if r.status_code == 404:
        return None, "failed", "404 not found"
    if r.status_code != 200:
        return None, "failed", f"HTTP {r.status_code}"

    soup = BeautifulSoup(r.text, "html.parser")
    body = extract_body(soup)
    body = clean_text(body)

    if len(body.split()) < 80:
        return body, "failed", f"body too short ({len(body.split())} words)"

    return body, "success", None


def run(limit=None, article_ids=None):
    """
    Download and extract body text for relevant, unprocessed rows.

    article_ids narrows the work to one run's articles. Without it every
    pending row is processed, which is right for a manual catch-up but
    wrong inside a pipeline run: a run that collected three articles
    would sit downloading the whole backlog a second at a time, and the
    result would be recorded against that run.
    """
    if article_ids is not None and not article_ids:
        print("Processing 0 articles...")
        return {"processed": 0, "success": 0, "failed": 0}

    query = (
        get_client().table("articles")
        .select("id, url")
        .eq("llm_relevant", True)
        .eq("processing_status", "pending")
    )
    if article_ids is not None:
        query = query.in_("id", list(article_ids))
    if limit:
        query = query.limit(limit)

    response = query.execute()
    rows = response.data or []
    print(f"Processing {len(rows)} articles...")

    success = failed = 0
    for row in rows:
        body, status, note = fetch_and_extract(row["url"])
        update = {
            "clean_content": body,
            "processing_status": status,
            "processing_note": note,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        get_client().table("articles").update(update).eq("id", row["id"]).execute()

        marker = "+" if status == "success" else "-"
        print(f"  [{marker}] {status:<10} {row['url'][:80]}")
        if status == "success":
            success += 1
        else:
            failed += 1

        time.sleep(1)  # be polite to servers

    print(f"\nDone. Success: {success}, Failed: {failed}.")
    return {"processed": len(rows), "success": success, "failed": failed}


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)