"""
/results and /search/comments: filters arrive as query params, bad ones
are refused with a reason, and a missing database degrades to a message
rather than a 500.
"""
from helpers import build_client
from orchestrator import corpus

ARTICLES = [
    {"id": 1, "title": "Teachers try AI tutors", "source": "Example News", "url": "https://example.com/1",
     "published_date": "2026-09-01T10:00:00+00:00", "clean_content": "Teachers say tutors help.",
     "source_type": "news_outlet", "stakeholder": "educators", "stable_topic_id": "T001", "topic": "Adoption",
     "sentiment": "positive"},
    {"id": 2, "title": "Students and cheating", "source": "A Blog", "url": "https://example.com/2",
     "published_date": "2026-08-01T10:00:00+00:00", "clean_content": "Cheating with chatbots rises.",
     "source_type": "blog", "stakeholder": "students", "stable_topic_id": "T004", "topic": "Integrity",
     "sentiment": "negative"},
]


def available():
    return {"available": True, "reason": None, "articles": ARTICLES}


class RecordingSearch:
    """Stands in for corpus.search_comments; remembers what it was asked."""

    def __init__(self, error=None):
        self.calls, self.error = [], error

    def __call__(self, articles, q):
        self.calls.append(([a["id"] for a in articles], q))
        if self.error:
            raise self.error
        return {"available": True, "reason": None, "total": 1,
                "comments": [{"comment_id": "c1", "article_id": articles[0]["id"], "snippet": q}]}


def test_results_without_filters_lists_the_whole_corpus():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results").get_json()
    assert (body["articles"]["total"], body["articles"]["corpus"]) == (2, 2)
    assert [a["id"] for a in body["articles"]["items"]] == [1, 2]
    assert body["sentiment_distribution"] == {"positive": 0.5, "neutral": 0, "negative": 0.5}
    assert body["analysed"] == 2 and body["sentiment_reason"] is None
    assert body["filter_options"]["stakeholders"] == ["educators", "students"]


def test_results_applies_the_filters_to_articles_and_topics():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results?stakeholder=students&q=cheating").get_json()
    assert [a["id"] for a in body["articles"]["items"]] == [2]
    assert body["articles"]["items"][0]["snippet"] == "Cheating with chatbots rises."
    assert body["top_topics"]["items"] == [{"label": "Integrity", "count": 1}]
    assert "clean_content" not in body["articles"]["items"][0]
    assert body["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 1.0}
    assert [r["label"] for r in body["sentiment_by_stakeholder"]] == ["students"]


def test_results_refuses_a_bad_date():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    response = client.get("/api/v1/results?from=yesterday")
    assert response.status_code == 400
    assert "'from' must be a date" in response.get_json()["error"]


def test_results_without_a_database_still_loads_and_says_why():
    client, _ = build_client(read_corpus=lambda: corpus.unavailable("Database down."),
                             search_comments=RecordingSearch())
    response = client.get("/api/v1/results")
    assert response.status_code == 200
    body = response.get_json()
    assert body["articles"]["available"] is False
    assert body["articles"]["reason"] == "Database down."
    assert body["top_topics"]["available"] is False
    assert body["analysed"] == 0 and body["sentiment_reason"] == "Database down."


def test_filters_that_match_nothing_give_empty_figures_with_the_reason():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results?stakeholder=parents").get_json()
    assert body["analysed"] == 0
    assert body["sentiment_reason"] == "No analysed articles match these filters."


def test_comment_search_needs_a_query():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    response = client.get("/api/v1/search/comments?stakeholder=students")
    assert response.status_code == 400
    assert response.get_json()["error"] == "'q' is required."


def test_comment_search_is_scoped_by_the_other_filters_but_not_by_q():
    search = RecordingSearch()
    client, _ = build_client(read_corpus=available, search_comments=search)
    # Article 1 never says "cheating", but its comments may.
    body = client.get("/api/v1/search/comments?q=cheating&stakeholder=educators").get_json()
    assert search.calls == [([1], "cheating")]
    assert body["total"] == 1


def test_a_failed_comment_search_is_reported_not_raised():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch(error=ConnectionError("down")))
    response = client.get("/api/v1/search/comments?q=cheating")
    assert response.status_code == 200
    assert response.get_json() == {"available": False, "total": 0, "comments": [],
                                   "reason": "Could not search comments; see the backend log."}


def test_comment_search_without_a_database_says_why():
    search = RecordingSearch()
    client, _ = build_client(read_corpus=lambda: corpus.unavailable("Database down."), search_comments=search)
    body = client.get("/api/v1/search/comments?q=cheating").get_json()
    assert (body["available"], body["reason"]) == (False, "Database down.")
    assert search.calls == []


def test_without_supabase_the_dashboard_says_it_is_not_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    client, _ = build_client()
    body = client.get("/api/v1/results").get_json()
    assert body["articles"]["reason"] == corpus.NOT_CONFIGURED
    assert body["top_topics"]["reason"] == corpus.NOT_CONFIGURED
