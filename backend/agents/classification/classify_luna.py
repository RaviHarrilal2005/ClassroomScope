# classify_luna.py
"""LLM-based stakeholder and source-type classification using GPT-5.6-Luna.
Writes results to classification_results with classifier = 'gpt-5.6-luna'.
Usage:
    python classify_luna.py 10      # test on 10 articles
    python classify_luna.py         # process all pending
"""

import os
import sys
import time
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

from ..supabase_client import get_client

load_dotenv()

API_KEY = os.getenv("TRUSSED_API_KEY")
BASE_URL = os.getenv("TRUSSED_BASE_URL")
MODEL = "gpt-5.6-luna"
CLASSIFIER_TAG = "gpt-5.6-luna"

STAKEHOLDER_CATEGORIES = [
    "students", "educators", "administrators",
    "policymakers", "parents", "researchers",
]

# Same domain map as the baseline, for source_type.
SOURCE_TYPE_DOMAINS = {
    "news_outlet": [
        "edweek.org", "insidehighered.com", "highereddive.com",
        "hechingerreport.org", "nytimes.com", "washingtonpost.com",
        "theguardian.com", "politico.com", "edsurge.com",
    ],
    "trade_publication": ["eschoolnews.com", "educationdive.com"],
    "academic": [".edu"],
    "government": [".gov"],
}


def classify_source_type(url):
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for stype, patterns in SOURCE_TYPE_DOMAINS.items():
        for pattern in patterns:
            if pattern in host:
                return stype, 0.95
    return "blog", 0.5


def build_prompt(title, content):
    categories = ", ".join(STAKEHOLDER_CATEGORIES)
    return f"""You are classifying a news article about generative AI in education.

	Classify the article into exactly ONE stakeholder category from this list:
	{categories}
	Or "undetermined" if none clearly applies.

	Definition: the stakeholder category is who the article is PRIMARILY ABOUT
	(not who wrote it, not who it is written for).

	Article title: {title}

	Article text:
	{content[:8000]}

	Respond with JSON only, no other text:
	{{"category": "<one category>", "confidence": <0.0-1.0>}}"""


def call_luna(prompt):
    """Send prompt to Luna, return (category, confidence) or (None, None)."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise text classifier. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 100,
        "reasoning_effort": "none",
    }

    try:
        r = requests.post(
            BASE_URL, headers=headers, json=body, timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return None, None, f"request failed: {e}"

    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        return None, None, f"unexpected response: {data}"

    # Tolerate markdown-fenced JSON.
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()

    try:
        parsed = json.loads(text)
        return parsed.get("category"), float(parsed.get("confidence", 0.0)), None
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return None, None, f"parse failed: {e} | raw: {text[:120]}"


def run(limit=None):
    if not API_KEY or not BASE_URL:
        print("TRUSSED_API_KEY or TRUSSED_BASE_URL missing from .env")
        return

    # Only articles not yet classified by Luna.
    existing = (
        get_client().table("classification_results")
        .select("article_id")
        .eq("classifier", CLASSIFIER_TAG)
        .execute()
    ).data or []
    done_ids = {r["article_id"] for r in existing}

    query = (
        get_client().table("articles")
        .select("id, title, clean_content, url")
        .eq("is_relevant", True)
        .eq("processing_status", "success")
    )
    if limit:
        query = query.limit(limit)
    rows = query.execute().data or []
    rows = [r for r in rows if r["id"] not in done_ids]

    print(f"Classifying {len(rows)} articles with {MODEL}...")

    success = failed = 0
    for i, row in enumerate(rows, 1):
        prompt = build_prompt(row.get("title"), row.get("clean_content") or "")
        category, confidence, error = call_luna(prompt)

        if category is None:
            print(f"  [{i}/{len(rows)}] FAILED: {error}")
            failed += 1
            time.sleep(0.5)
            continue

        source_type, source_conf = classify_source_type(row["url"])
        record = {
            "article_id": row["id"],
            "stakeholder_category": category,
            "confidence": confidence,
            "source_type": source_type,
            "source_type_confidence": source_conf,
            "classifier": CLASSIFIER_TAG,
            "classified_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            get_client().table("classification_results").upsert(
                record, on_conflict="article_id,classifier"
            ).execute()
            success += 1
            if i % 10 == 0 or i == len(rows):
                print(f"  [{i}/{len(rows)}] {category} ({confidence:.2f})")
        except Exception as e:
            print(f"  [{i}/{len(rows)}] DB write failed: {e}")
            failed += 1

        time.sleep(0.3)  # be polite to the endpoint

    print(f"\nDone. Success: {success}, Failed: {failed}.")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)