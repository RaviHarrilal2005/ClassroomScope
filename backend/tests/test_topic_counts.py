"""
The dashboard's topic counts.

What can go wrong here is quiet: unassigned articles counted as a topic,
or no topics drawn as an empty chart.
"""
from orchestrator.topic_counts import top_topics


def row(stable_topic_id, topic=None):
    return {"stable_topic_id": stable_topic_id, "topic": topic}


def test_counts_articles_per_topic_most_frequent_first():
    rows = [row("T004", "Integrity")] * 3 + [row("T002", "Restrictions")] * 2 \
        + [row("T001", "Adoption")] * 2 + [row(None, "Unassigned")] * 4
    assert top_topics(rows) == {
        "available": True,
        "reason": None,
        "counted": 7,
        "unassigned": 4,
        # Equal counts fall back to the label, so the bars keep their order.
        "items": [
            {"label": "Integrity", "count": 3},
            {"label": "Adoption", "count": 2},
            {"label": "Restrictions", "count": 2},
        ],
    }


def test_no_rows_is_unavailable_rather_than_an_empty_chart():
    empty = top_topics([])
    assert empty["available"] is False
    assert "no rows" in empty["reason"]

    none_assigned = top_topics([row(None)] * 3)
    assert none_assigned["available"] is False
    assert "3" in none_assigned["reason"]
