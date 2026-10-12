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
