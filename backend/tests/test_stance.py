"""The stance agent, offline: Luna's call is replaced, the database is a FakeSupabase."""
import pytest

from fake_supabase import FakeSupabase
from agents.stance import stance_agent as agent


def article(id, content="Schools are adopting AI tutors."):
    return {"id": id, "title": f"Article {id}", "clean_content": content, "content_hash": f"h{id}",
            "llm_relevant": True, "processing_status": "success"}


@pytest.fixture
def database(monkeypatch):
    db = FakeSupabase(articles=[article(1), article(2), article(3)],
                      stance_results=[{"article_id": 1, "stance": "against", "method": agent.METHOD}])
    monkeypatch.setattr(agent, "get_client", lambda: db)
    return db


def answers(monkeypatch, *replies):
    """Luna replies, in order: (label, confidence, error)."""
    queue = list(replies)
    monkeypatch.setattr(agent.luna, "call_luna", lambda prompt: queue.pop(0))


def test_labels_only_articles_without_a_stance_and_records_target_and_method(database, monkeypatch):
    answers(monkeypatch, (" Favor", 0.91234, None), ("neutral", 0.6, None))
    summary = agent.run_stance(call_interval=0)
    assert summary["skipped_existing"] == 1 and summary["processed"] == 2
    assert database.tables["stance_results"][1:] == [
        {"article_id": 2, "stance": "favor", "confidence": 0.912, "target": agent.TARGET, "method": agent.METHOD},
        {"article_id": 3, "stance": "neutral", "confidence": 0.6, "target": agent.TARGET, "method": agent.METHOD},
    ]


def test_an_unknown_label_is_a_failure_not_a_stance(database, monkeypatch):
    answers(monkeypatch, ("supportive", 0.9, None), ("against", 0.8, None))
    summary = agent.run_stance(call_interval=0)
    assert summary["failed_ids"] == [2] and summary["processed"] == 1


def test_every_call_failing_raises_so_the_coordinator_retries(database, monkeypatch):
    answers(monkeypatch, (None, None, "request failed: 401"), (None, None, "request failed: 401"))
    with pytest.raises(RuntimeError, match="401"):
        agent.run_stance(call_interval=0)


def test_no_approved_articles_reads_nothing(monkeypatch):
    monkeypatch.setattr(agent, "get_client", lambda: pytest.fail("should not connect"))
    assert agent.run_stance(article_ids=[])["processed"] == 0
