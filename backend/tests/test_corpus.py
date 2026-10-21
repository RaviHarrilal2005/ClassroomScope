"""
The dashboard's corpus: which articles count, what each one is labelled,
and how filters and search narrow them.

What goes wrong here is quiet: an irrelevant article counted, the keyword
baseline overriding the LLM's label, a capped page dropping rows, or a
`%` in a search matching everything.
"""
import pytest

from fake_supabase import FakeSupabase
from orchestrator import corpus


def article(id, title="An article", date="2026-09-01T10:00:00+00:00", content="Some text.",
            relevant=True, status="success", **extra):
    return {"id": id, "title": title, "source": "Example News", "url": f"https://example.com/{id}",
            "published_date": date, "clean_content": content, "llm_relevant": relevant,
            "processing_status": status, **extra}


def classified(article_id, classifier, stakeholder, source_type="blog", at="2026-09-18T00:00:00+00:00", id=None):
    return {"id": id or article_id * 10 + len(classifier), "article_id": article_id, "classifier": classifier,
            "stakeholder_category": stakeholder, "source_type": source_type, "classified_at": at}


def topic(article_id, stable_topic_id, label=None, id=None):
    return {"id": id or article_id, "article_id": article_id, "stable_topic_id": stable_topic_id, "topic": label}


def corpus_row(id, **fields):
    """A merged corpus article, as read_corpus returns it."""
    row = {"id": id, "title": f"Article {id}", "source": "Example News", "url": f"https://example.com/{id}",
           "published_date": "2026-09-01T10:00:00+00:00", "clean_content": "Some text.",
           "source_type": "blog", "stakeholder": "students", "stable_topic_id": None, "topic": None}
    row.update(fields)
    return row


NO_FILTERS = {key: "" for key in ("from", "to", "source_type", "stakeholder", "topic", "q")}


def filters(**set_values):
    return {**NO_FILTERS, **set_values}


# --- read_corpus ----------------------------------------------------------

def test_only_analysable_articles_are_read():
    client = FakeSupabase(articles=[
        article(1), article(2, relevant=False), article(3, status="failed"), article(4, relevant=None),
    ])
    assert [a["id"] for a in corpus.read_corpus(client)] == [1]


def test_a_real_classifier_beats_the_keyword_baseline_even_when_older():
    client = FakeSupabase(
        articles=[article(1), article(2)],
        classification_results=[
            classified(1, "gpt-5.6-luna", "educators", "news_outlet", at="2026-09-01T00:00:00+00:00"),
            classified(1, "baseline_keyword", "students", "blog", at="2026-10-01T00:00:00+00:00"),
            classified(2, "baseline_keyword", "parents", "academic"),
        ],
    )
    by_id = {a["id"]: a for a in corpus.read_corpus(client)}
    assert (by_id[1]["stakeholder"], by_id[1]["source_type"]) == ("educators", "news_outlet")
    # Baseline is still used when it is all there is.
    assert (by_id[2]["stakeholder"], by_id[2]["source_type"]) == ("parents", "academic")


def test_an_unclassified_article_has_no_labels():
    a = corpus.read_corpus(FakeSupabase(articles=[article(1)]))[0]
    assert (a["stakeholder"], a["source_type"], a["stable_topic_id"], a["topic"]) == (None, None, None, None)


def test_the_newest_topic_row_wins_and_no_stable_id_means_unassigned():
    client = FakeSupabase(
        articles=[article(1), article(2)],
        topic_results=[
            topic(1, "T001", "Old label", id=1),
            topic(1, "T004", "Integrity", id=9),
            topic(2, None, "Outliers", id=5),
        ],
    )
    by_id = {a["id"]: a for a in corpus.read_corpus(client)}
    assert (by_id[1]["stable_topic_id"], by_id[1]["topic"]) == ("T004", "Integrity")
    assert (by_id[2]["stable_topic_id"], by_id[2]["topic"]) == (None, None)


def sentiment(article_id, label, method="roberta_news", id=None):
    return {"id": id or article_id, "article_id": article_id, "sentiment": label, "method": method}


def test_roberta_beats_vader_whatever_the_row_order_and_no_row_means_none():
    client = FakeSupabase(
        articles=[article(1), article(2), article(3)],
        sentiment_results=[
            sentiment(1, "positive", id=1), sentiment(1, "negative", "vader", id=9),
            sentiment(2, "neutral", "vader", id=2), sentiment(2, "negative", "vader", id=8),
        ],
    )
    by_id = {a["id"]: a["sentiment"] for a in corpus.read_corpus(client)}
    assert by_id == {1: "positive", 2: "negative", 3: None}


def test_every_sentiment_page_is_read_even_when_the_server_caps_pages():
    client = FakeSupabase(cap=2, articles=[article(i) for i in range(1, 6)],
                          sentiment_results=[sentiment(i, "neutral") for i in range(1, 6)])
    assert [a["sentiment"] for a in corpus.read_corpus(client)] == ["neutral"] * 5


def test_every_page_is_read_even_when_the_server_caps_pages():
    client = FakeSupabase(cap=2, articles=[article(i) for i in range(1, 6)],
                          topic_results=[topic(i, "T001", "Adoption") for i in range(1, 6)])
    rows = corpus.read_corpus(client)
    assert len(rows) == 5
    assert all(r["stable_topic_id"] == "T001" for r in rows)


def test_missing_text_reads_as_empty():
    a = corpus.read_corpus(FakeSupabase(articles=[article(1, content=None)]))[0]
    assert a["clean_content"] == ""


# --- reader -----------------------------------------------------------------

def test_reader_caches_until_the_ttl_passes():
    now = [0.0]
    client = FakeSupabase(articles=[article(1)])
    read = corpus.reader(client, ttl=60, clock=lambda: now[0])

    assert read()["available"] is True
    opened = len(client.opened)
    now[0] = 59
    read()
    assert len(client.opened) == opened  # served from the cache
    now[0] = 61
    read()
    assert len(client.opened) == 2 * opened


def test_a_failed_read_is_reported_and_retried_next_time():
    client = FakeSupabase(articles=[article(1)], error=ConnectionError("network down"))
    read = corpus.reader(client, ttl=60, clock=lambda: 0.0)

    first = read()
    assert first == {"available": False, "reason": "Could not read the articles; see the backend log.",
                     "articles": []}
    client.error = None
    assert read()["available"] is True  # the failure was not cached


# --- parse_filters --------------------------------------------------------

def test_filters_default_to_empty_and_are_trimmed():
    assert corpus.parse_filters({}) == NO_FILTERS
    assert corpus.parse_filters({"stakeholder": "  educators ", "q": " cheating "})["q"] == "cheating"


@pytest.mark.parametrize("args, message", [
    ({"from": "08/10/2026"}, "'from' must be a date"),
    ({"to": "2026-13-01"}, "'to' must be a date"),
    ({"from": "2026-10-02", "to": "2026-10-01"}, "'from' must not be after 'to'"),
    ({"q": "a"}, "2 to 100 characters"),
    ({"q": "x" * 101}, "2 to 100 characters"),
])
def test_bad_filters_are_rejected_with_a_reason(args, message):
    with pytest.raises(ValueError, match=message):
        corpus.parse_filters(args)


def test_dates_are_normalised_so_they_compare_as_text():
    assert corpus.parse_filters({"from": "2026-1-5"})["from"] == "2026-01-05"


# --- filter_articles --------------------------------------------------------

def test_date_range_is_inclusive_and_undated_articles_drop_out_only_when_dates_are_set():
    rows = [corpus_row(1, published_date="2026-09-01T23:59:00+00:00"),
            corpus_row(2, published_date="2026-09-02T00:00:00+00:00"),
            corpus_row(3, published_date=None)]
    assert [a["id"] for a in corpus.filter_articles(rows, filters(**{"from": "2026-09-01", "to": "2026-09-01"}))] == [1]
    assert [a["id"] for a in corpus.filter_articles(rows, filters(**{"from": "2026-09-02"}))] == [2]
    assert {a["id"] for a in corpus.filter_articles(rows, NO_FILTERS)} == {1, 2, 3}


def test_exact_filters_combine():
    rows = [corpus_row(1, source_type="blog", stakeholder="students", stable_topic_id="T001"),
            corpus_row(2, source_type="blog", stakeholder="educators", stable_topic_id="T001"),
            corpus_row(3, source_type="news_outlet", stakeholder="students", stable_topic_id="T001"),
            corpus_row(4, source_type="blog", stakeholder="students", stable_topic_id="T002")]
    got = corpus.filter_articles(rows, filters(source_type="blog", stakeholder="students", topic="T001"))
    assert [a["id"] for a in got] == [1]


def test_newest_first_and_undated_last():
    rows = [corpus_row(1, published_date=None),
            corpus_row(2, published_date="2026-01-01T00:00:00+00:00"),
            corpus_row(3, published_date="2026-06-01T00:00:00+00:00")]
    assert [a["id"] for a in corpus.filter_articles(rows, NO_FILTERS)] == [3, 2, 1]


def test_search_ignores_case_and_snips_around_the_first_match():
    text = "A" * 200 + " Students admit CHEATING with chatbots. " + "B" * 200
    rows = [corpus_row(1, clean_content=text), corpus_row(2, clean_content="Nothing relevant.")]
    got = corpus.filter_articles(rows, filters(q="cheating"))
    assert [a["id"] for a in got] == [1]
    snippet = got[0]["snippet"]
    assert "CHEATING" in snippet
    assert snippet.startswith("…") and snippet.endswith("…")
    assert len(snippet) < 200


def test_a_title_only_match_counts_but_has_no_snippet():
    got = corpus.filter_articles([corpus_row(1, title="Cheating scandal", clean_content="Nothing here.")],
                                 filters(q="cheating"))
    assert [(a["id"], a["snippet"]) for a in got] == [(1, None)]


def test_a_search_survives_missing_titles_and_text():
    rows = [corpus_row(1, title=None, clean_content="")]
    assert corpus.filter_articles(rows, filters(q="anything")) == []


def test_snippets_collapse_newlines_and_skip_ellipses_at_the_edges():
    assert corpus.make_snippet("Short\n\ntext about AI.", "ai") == "Short text about AI."
    assert corpus.make_snippet("no match here", "ai tutor") is None


# --- results_payload ------------------------------------------------------

def test_topics_are_counted_over_the_filtered_articles_only():
    rows = [corpus_row(1, stakeholder="students", stable_topic_id="T004", topic="Integrity"),
            corpus_row(2, stakeholder="students", stable_topic_id=None),
            corpus_row(3, stakeholder="educators", stable_topic_id="T001", topic="Adoption")]
    payload = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(stakeholder="students"))
    assert payload["top_topics"]["items"] == [{"label": "Integrity", "count": 1}]
    assert (payload["top_topics"]["counted"], payload["top_topics"]["unassigned"]) == (1, 1)
    assert (payload["articles"]["total"], payload["articles"]["corpus"]) == (2, 3)


def test_articles_go_out_without_their_text():
    rows = [corpus_row(1, clean_content="The whole article body.")]
    item = corpus.results_payload({"available": True, "reason": None, "articles": rows}, NO_FILTERS)["articles"]["items"][0]
    assert "clean_content" not in item
    assert set(item) == set(corpus.ARTICLE_FIELDS)


def test_filter_options_come_from_the_whole_corpus():
    rows = [corpus_row(1, source_type="blog", stakeholder="students", stable_topic_id="T004", topic="Integrity",
                       published_date="2026-02-01T00:00:00+00:00"),
            corpus_row(2, source_type="academic", stakeholder=None, stable_topic_id="T001", topic="Adoption",
                       published_date="2025-11-30T00:00:00+00:00")]
    options = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(source_type="blog"))["filter_options"]
    assert options == {
        "source_types": ["academic", "blog"],
        "stakeholders": ["students"],
        "topics": [{"id": "T001", "label": "Adoption"}, {"id": "T004", "label": "Integrity"}],
        "date_min": "2025-11-30",
        "date_max": "2026-02-01",
    }


def test_no_matches_says_so_instead_of_drawing_an_empty_chart():
    rows = [corpus_row(1, stakeholder="students")]
    payload = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(stakeholder="parents"))
    assert payload["top_topics"]["available"] is False
    assert payload["top_topics"]["reason"] == "No articles match these filters."
    assert payload["articles"]["items"] == []


def test_an_unavailable_corpus_gives_the_same_shape_with_a_reason():
    payload = corpus.results_payload(corpus.unavailable("Database down."), NO_FILTERS)
    assert payload["articles"] == {"available": False, "reason": "Database down.", "total": 0, "corpus": 0, "items": []}
    assert payload["top_topics"]["reason"] == "Database down."
    assert payload["filter_options"]["topics"] == []


# --- search_comments ------------------------------------------------------

def comment(comment_id, article_id, body, created="2026-09-01T00:00:00+00:00", recommends=0):
    return {"comment_id": comment_id, "article_id": article_id, "body_text": body,
            "created_at": created, "recommendation_count": recommends}


def test_comments_are_searched_only_on_the_given_articles_newest_first():
    client = FakeSupabase(comments=[
        comment("c1", 1, "Cheating is rampant", created="2026-09-01T00:00:00+00:00"),
        comment("c2", 1, "cheating again", created="2026-09-03T00:00:00+00:00", recommends=4),
        comment("c3", 2, "Cheating elsewhere"),
        comment("c4", 1, "Unrelated"),
    ])
    got = corpus.search_comments(client, [corpus_row(1, title="AI in class")], "CHEATING")
    assert got["total"] == 2
    assert [c["comment_id"] for c in got["comments"]] == ["c2", "c1"]
    assert got["comments"][0] == {"comment_id": "c2", "article_id": 1, "article_title": "AI in class",
                                  "created_at": "2026-09-03T00:00:00+00:00", "recommendation_count": 4,
                                  "snippet": "cheating again"}


def test_the_total_counts_every_match_but_only_the_limit_comes_back():
    client = FakeSupabase(comments=[comment(f"c{i}", 1, "chatbot") for i in range(60)])
    got = corpus.search_comments(client, [corpus_row(1)], "chatbot")
    assert (got["total"], len(got["comments"])) == (60, corpus.COMMENT_LIMIT)


@pytest.mark.parametrize("q, pattern", [
    ("50%", "%50\\%%"),
    ("snake_case", "%snake\\_case%"),
    ("back\\slash", "%back\\\\slash%"),
])
def test_like_wildcards_in_a_search_match_literally(q, pattern):
    client = FakeSupabase(comments=[comment("c1", 1, f"about {q} here"), comment("c2", 1, "something else")])
    got = corpus.search_comments(client, [corpus_row(1)], q)
    assert client.patterns == [pattern]
    assert [c["comment_id"] for c in got["comments"]] == ["c1"]


def test_no_articles_means_no_query():
    client = FakeSupabase(comments=[comment("c1", 1, "chatbot")])
    assert corpus.search_comments(client, [], "chatbot") == {"available": True, "reason": None, "total": 0, "comments": []}
    assert client.opened == []


def test_without_supabase_both_readers_say_why(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    read, search = corpus.from_env()
    assert read() == corpus.unavailable(corpus.NOT_CONFIGURED)
    assert search([corpus_row(1)], "chatbot")["reason"] == corpus.NOT_CONFIGURED
