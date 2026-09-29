# classify_baseline.py
"""Keyword-based classification baseline (F.10 comparison point).
Two outputs per article: stakeholder_group + source_type.
"""

import re
from urllib.parse import urlparse
from datetime import datetime, timezone

from ..supabase_client import get_client

# Stakeholder keyword sets. Each article scores against all; highest wins.
STAKEHOLDER_TERMS = {
    "students":     ["student", "undergrad", "graduate", "learner", "pupil"],
    "educators":    ["teacher", "professor", "faculty", "instructor", "educator"],
    "administrators": ["administrator", "dean", "principal", "provost", "university official"],
    "policymakers": ["policy", "lawmaker", "legislator", "regulation", "government"],
    "parents":      ["parent", "family", "guardian"],
    "researchers":  ["researcher", "study", "academic study", "scholar"],
}

CONFIDENCE_THRESHOLD = 0.15   # below this → 'undetermined'

# Source type by domain. Extend as you add outlets.
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
    return "blog", 0.5   # default fallback


def classify_stakeholder(title, content):
    text = f"{title or ''} {content or ''}".lower()
    if not text.strip():
        return "undetermined", 0.0

    scores = {}
    for group, terms in STAKEHOLDER_TERMS.items():
        hits = sum(text.count(term) for term in terms)
        scores[group] = hits

    total = sum(scores.values())
    if total == 0:
        return "undetermined", 0.0

    winner = max(scores, key=scores.get)
    confidence = scores[winner] / total

    if confidence < CONFIDENCE_THRESHOLD:
        return "undetermined", round(confidence, 3)
    return winner, round(confidence, 3)


def run(limit=None):
    query = (
        get_client().table("articles")
        .select("id, title, clean_content, url")
        .eq("is_relevant", True)
        .eq("processing_status", "success")
    )
    if limit:
        query = query.limit(limit)
    rows = query.execute().data or []
    print(f"Classifying {len(rows)} articles...")

    results = []
    for row in rows:
        group, conf = classify_stakeholder(row["title"], row["clean_content"])
        source_type, source_conf = classify_source_type(row["url"])
        results.append({
            "article_id": row["id"],
            "stakeholder_category": group,
            "confidence": conf,
            "source_type": source_type,
            "source_type_confidence": source_conf,
            "classifier": "baseline_keyword",
            "classified_at": datetime.now(timezone.utc).isoformat(),
        })

    # Insert in batches
    for i in range(0, len(results), 200):
        batch = results[i:i+200]
        get_client().table("classification_results").upsert(
            batch, on_conflict="article_id,classifier"
        ).execute()

    print(f"Wrote {len(results)} classification results.")


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)