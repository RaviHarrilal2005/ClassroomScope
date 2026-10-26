"""
The aggregation rules. What goes quietly wrong here: an article without a
sentiment deflating every share, a missing topic raising instead of being
skipped, an unknown label crashing the count, an empty corpus dividing by
zero.
"""
from typing import Optional

from agents.aggregation.compute import NO_SENTIMENT, sentiment_figures


def art(id, sentiment: Optional[str] = "neutral", month: Optional[str] = "2025-03", topic=None,
        stakeholder: Optional[str] = "educators"):
    return {"id": id, "published_date": f"{month}-10T10:00:00+00:00" if month else None,
            "topic": topic, "stakeholder": stakeholder, "sentiment": sentiment}


def test_distribution_is_shares_of_the_analysed_articles():
    arts = [art(1, "positive"), art(2, "neutral"), art(3, "neutral"), art(4, "negative")]
    result = sentiment_figures(arts)
    assert result["sentiment_distribution"] == {"positive": 0.25, "neutral": 0.5, "negative": 0.25}
    assert result["analysed"] == 4 and result["sentiment_reason"] is None


def test_articles_without_a_known_sentiment_are_left_out():
    result = sentiment_figures([art(1, "positive"), art(2, None), art(3, "mixed")])
    assert result["analysed"] == 1
    assert result["sentiment_distribution"] == {"positive": 1.0, "neutral": 0, "negative": 0}


def test_timeline_buckets_by_month_oldest_first_and_skips_undated():
    arts = [art(1, "positive", "2025-03"), art(2, "negative", "2024-11"), art(3, "neutral", None)]
    result = sentiment_figures(arts)
    assert [(m["label"], m["total"]) for m in result["sentiment_over_time"]] == [("2024-11", 1), ("2025-03", 1)]
    assert result["analysed"] == 3  # the undated article still counts in the totals


def test_by_topic_counts_each_topic_and_leaves_out_unassigned_articles():
    arts = [art(1, "positive", topic="Adoption"), art(2, "negative", topic="Adoption"), art(3, "neutral")]
    assert sentiment_figures(arts)["sentiment_by_topic"] == [
        {"label": "Adoption", "positive": 1, "neutral": 0, "negative": 1, "total": 2}]


def test_breakdowns_are_largest_first_then_by_label():
    arts = [art(1, stakeholder="students"), art(2, stakeholder="educators"), art(3, stakeholder="students")]
    assert [r["label"] for r in sentiment_figures(arts)["sentiment_by_stakeholder"]] == ["students", "educators"]


def test_an_article_without_a_stakeholder_is_undetermined():
    by = {r["label"]: r for r in sentiment_figures([art(1, "negative", stakeholder=None)])["sentiment_by_stakeholder"]}
    assert by["undetermined"]["negative"] == 1


def test_no_analysed_articles_gives_zeros_and_the_reason_not_an_error():
    result = sentiment_figures([art(1, None)], reason_if_empty="No articles match these filters.")
    assert result["analysed"] == 0
    assert result["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 0}
    assert result["sentiment_over_time"] == result["sentiment_by_topic"] == result["sentiment_by_stakeholder"] == []
    assert result["sentiment_reason"] == "No articles match these filters."
    assert sentiment_figures([])["sentiment_reason"] == NO_SENTIMENT


# --- the headline: which group and topic the news is most negative about ---

def group(label, negative, total, field="stakeholder", start=0):
    """`total` articles about `label`, the first `negative` of them negative."""
    return [art(start + i, "negative" if i < negative else "neutral", **{field: label}) for i in range(total)]


def test_most_negative_is_the_highest_negative_share_among_groups_with_enough_articles():
    arts = (group("students", 6, 20) + group("educators", 2, 20, start=100)
            + group("parents", 5, 5, start=200))  # 100% negative, but too few to name
    assert sentiment_figures(arts)["most_negative_stakeholder"]["label"] == "students"


def test_most_negative_works_for_topics_too():
    arts = group("Integrity", 1, 20, field="topic") + group("Policy", 9, 20, field="topic", start=100)
    assert sentiment_figures(arts)["most_negative_topic"]["label"] == "Policy"


def test_no_most_negative_with_fewer_than_two_groups_to_compare():
    arts = group("students", 6, 20) + group("parents", 5, 5, start=100)
    assert sentiment_figures(arts)["most_negative_stakeholder"] is None


def test_undetermined_is_never_named_most_negative():
    arts = group(None, 20, 20) + group("students", 1, 20, start=100) + group("educators", 0, 20, start=200)
    assert sentiment_figures(arts)["most_negative_stakeholder"]["label"] == "students"


def test_no_most_negative_when_nothing_is_negative():
    arts = group("students", 0, 20) + group("educators", 0, 20, start=100)
    assert sentiment_figures(arts)["most_negative_stakeholder"] is None
