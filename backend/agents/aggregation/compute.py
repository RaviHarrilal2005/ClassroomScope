"""
The aggregation rules, as pure functions.

No database, no network, no clock: corpus articles in (one merged row per
article, see orchestrator/corpus.py), dashboard figures out, so every
counting decision can be tested without a fake Supabase.

Only articles with a known sentiment count. Articles without one are
still in the article list and the topic counts; counting them here would
deflate every share.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

SENTIMENTS = ("positive", "neutral", "negative")
UNDETERMINED = "undetermined"
NO_SENTIMENT = "No sentiment results yet."
# ponytail: a fixed cutoff, not a significance test. Below it one article
# swings a share by 5+ points, so a group that small is never named.
MIN_ARTICLES_TO_NAME = 20

Row = Dict[str, Any]


def _zero_counts() -> Dict[str, int]:
    return {s: 0 for s in SENTIMENTS}


def _breakdown(pairs: Iterable[Tuple[str, str]], by_label: bool = False) -> List[Row]:
    """(label, sentiment) pairs -> one row per label with a count per sentiment, largest first."""
    rows: Dict[str, Row] = {}
    for label, sentiment in pairs:
        row = rows.setdefault(label, {"label": label, **_zero_counts(), "total": 0})
        row[sentiment] += 1
        row["total"] += 1
    if by_label:
        return sorted(rows.values(), key=lambda r: r["label"])
    return sorted(rows.values(), key=lambda r: (-r["total"], r["label"]))


def _most_negative(rows: List[Row]) -> Optional[Row]:
    """
    The breakdown row with the highest negative share, for the dashboard's
    headline. None unless at least two rows have enough articles to compare
    and one of them has a negative article; undetermined is never named.
    """
    named = [r for r in rows if r["label"] != UNDETERMINED and r["total"] >= MIN_ARTICLES_TO_NAME]
    if len(named) < 2:
        return None
    top = max(named, key=lambda r: (r["negative"] / r["total"], r["total"]))
    return top if top["negative"] else None


def sentiment_figures(articles: Iterable[Row], reason_if_empty: str = NO_SENTIMENT) -> Row:
    """The sentiment share, its breakdowns by month, topic and stakeholder, and the most negative of each."""
    analysed = [a for a in articles if a.get("sentiment") in SENTIMENTS]
    counts = _zero_counts()
    for a in analysed:
        counts[a["sentiment"]] += 1
    total = len(analysed)
    reason: Optional[str] = None if total else reason_if_empty
    by_topic = _breakdown((a["topic"], a["sentiment"]) for a in analysed if a.get("topic"))
    by_stakeholder = _breakdown((a.get("stakeholder") or UNDETERMINED, a["sentiment"]) for a in analysed)
    return {
        "analysed": total,
        "sentiment_distribution": {s: (counts[s] / total if total else 0) for s in SENTIMENTS},
        "sentiment_over_time": _breakdown(((a["published_date"][:7], a["sentiment"])
                                           for a in analysed if a.get("published_date")), by_label=True),
        "sentiment_by_topic": by_topic,
        "sentiment_by_stakeholder": by_stakeholder,
        "most_negative_topic": _most_negative(by_topic),
        "most_negative_stakeholder": _most_negative(by_stakeholder),
        "sentiment_reason": reason,
    }
