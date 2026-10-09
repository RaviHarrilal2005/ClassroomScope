"""
The retraining script's guardrails, without training anything.

train_auto imports the topic module, which loads BERTopic, so a stand-in
module takes its place, and build_model is replaced with a fake model
that "trains" instantly. What is under test is what TOPIC_IDENTITY.md
promises: a candidate never overwrites another, a failure is recorded,
and the counts in training.json are true.
"""
import hashlib
import importlib
import json
import sys
import types

import pandas as pd
import pytest


def articles(n):
    return pd.DataFrame({"id": range(1, n + 1), "clean_content": [f"article {i}" for i in range(n)]})


class FakeModel:
    def __init__(self, topics=None, error=None):
        self.topics, self.error = topics, error

    def fit_transform(self, documents):
        if self.error:
            raise self.error
        assert len(documents) == len(self.topics)
        return self.topics, None

    def save(self, path, serialization):
        assert serialization == "pickle"
        with open(path, "wb") as f:
            f.write(b"saved model")

    def get_topic_info(self):
        counts = pd.Series(self.topics).value_counts().sort_index()
        return pd.DataFrame({"Topic": counts.index, "Count": counts.values})

    def get_topic(self, topic):
        return [(f"word{topic}", 0.5), (f"term{topic}", 0.25)]


@pytest.fixture
def train_auto(monkeypatch, tmp_path):
    topic_model = types.ModuleType("agents.topic.topic_model")
    topic_model.load_articles = lambda: articles(12)
    topic_model.eligible_articles = lambda frame: frame
    monkeypatch.setitem(sys.modules, "agents.topic.topic_model", topic_model)
    monkeypatch.delitem(sys.modules, "agents.topic.train_auto", raising=False)
    module = importlib.import_module("agents.topic.train_auto")
    monkeypatch.setattr(module, "MODELS_DIR", tmp_path)
    return module


def manifest(path):
    return json.loads((path / "training.json").read_text())


def test_a_candidate_is_saved_with_its_topics_and_manifest(train_auto, tmp_path, monkeypatch):
    topics = [0, 0, 1, 1, -1, 0, 1, 0, 0, 1, -1, 2]
    monkeypatch.setattr(train_auto, "build_model", lambda min_topic_size: FakeModel(topics))

    train_auto.train("auto-v1")

    out = tmp_path / "auto-v1"
    record = manifest(out)
    assert record["status"] == "succeeded"
    assert (record["articles"], record["topics"], record["unassigned"]) == (12, 3, 2)
    assert record["model_sha256"] == hashlib.sha256(b"saved model").hexdigest()
    assert record["settings"]["nr_topics"] is None
    assignments = pd.read_csv(out / "assignments.csv")
    assert assignments["article_id"].tolist() == list(range(1, 13))
    assert assignments["topic_id"].tolist() == topics
    assert pd.read_csv(out / "topics.csv")["topic_id"].tolist() == [-1, 0, 1, 2]


def test_an_existing_version_is_never_overwritten(train_auto, tmp_path, monkeypatch):
    existing = tmp_path / "auto-v1"
    existing.mkdir()
    (existing / "model.pkl").write_bytes(b"reviewed candidate")
    monkeypatch.setattr(train_auto, "build_model", lambda min_topic_size: pytest.fail("trained anyway"))

    with pytest.raises(FileExistsError):
        train_auto.train("auto-v1")
    assert (existing / "model.pkl").read_bytes() == b"reviewed candidate"


def test_a_failed_training_keeps_its_folder_marked_failed(train_auto, tmp_path, monkeypatch):
    monkeypatch.setattr(train_auto, "build_model",
                        lambda min_topic_size: FakeModel(error=RuntimeError("out of memory")))

    with pytest.raises(RuntimeError):
        train_auto.train("auto-v2")
    record = manifest(tmp_path / "auto-v2")
    assert record["status"] == "failed"
    assert "out of memory" in record["error"]


def test_too_few_articles_fails_instead_of_inventing_topics(train_auto, tmp_path, monkeypatch):
    monkeypatch.setattr(train_auto, "load_articles", lambda: articles(5))
    monkeypatch.setattr(train_auto, "build_model", lambda min_topic_size: pytest.fail("trained anyway"))

    with pytest.raises(ValueError, match="at least"):
        train_auto.train("auto-v3")
    assert manifest(tmp_path / "auto-v3")["status"] == "failed"


def test_bad_arguments_are_refused_before_anything_is_written(train_auto, tmp_path):
    for version in ("../escape", "a/b", "a\\b", "", ".hidden"):
        with pytest.raises(ValueError):
            train_auto.train(version)
    with pytest.raises(ValueError):
        train_auto.train("auto-v4", min_topic_size=1)
    assert list(tmp_path.iterdir()) == []
