"""
The dashboard's topic counts, read straight from topic_results.

What can go wrong here is quiet: a page cap that drops rows, unassigned
articles counted as a topic, or an empty table drawn as an empty chart.
"""
from types import SimpleNamespace

from helpers import build_client
from orchestrator.topic_counts import reader, read_topic_rows, top_topics


def row(stable_topic_id, topic=None):
    return {"stable_topic_id": stable_topic_id, "topic": topic}


class FakeClient:
    """topic_results behind PostgREST, which returns at most `cap` rows a request."""

    def __init__(self, rows, cap=1000, error=None):
        self.rows, self.cap, self.error = rows, cap, error

    def table(self, name):
        assert name == "topic_results"
        return self

    def select(self, columns):
        return self

    def order(self, column):
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def execute(self):
        if self.error:
            raise self.error
        start, end = self.window
        return SimpleNamespace(data=self.rows[start:min(end + 1, start + self.cap)])


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


def test_reads_every_page_even_when_the_server_caps_pages():
    rows = [row("T001", "Adoption")] * 5
    assert len(read_topic_rows(FakeClient(rows, cap=2))) == 5


def test_no_rows_is_unavailable_rather_than_an_empty_chart():
    empty = top_topics([])
    assert empty["available"] is False
    assert "no rows" in empty["reason"]

    none_assigned = top_topics([row(None)] * 3)
    assert none_assigned["available"] is False
    assert "3" in none_assigned["reason"]


def test_a_failed_read_is_reported_instead_of_breaking_the_endpoint():
    facet = reader(FakeClient([], error=ConnectionError("network down")))()
    assert facet["available"] is False
    assert "Could not read topic_results" in facet["reason"]


def test_results_serves_the_counts():
    facet = top_topics([row("T004", "Integrity")])
    client, _ = build_client(read_topics=lambda: facet)
    assert client.get("/api/v1/results").get_json()["top_topics"] == facet


def test_results_says_why_topics_are_missing_without_supabase(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    client, _ = build_client()
    topics = client.get("/api/v1/results").get_json()["top_topics"]
    assert topics["available"] is False
    assert "not configured" in topics["reason"]
