"""
Which agent the registry picks for each stage.

The choice depends on the environment, which makes it exactly the kind
of thing that silently goes wrong: a placeholder key that reads as
'configured', or a test suite that behaves differently on the one
machine that happens to have a .env.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

from agents.adapters import ClassificationAgent, CollectionAgent, TopicAgent
from orchestrator.agents import StubAgent
from orchestrator.registry import _luna_configured, build_default_registry
from orchestrator.stages import (
    AGGREGATION,
    CLASSIFICATION,
    COLLECTION,
    PIPELINE_ORDER,
    SECURITY,
    SENTIMENT,
    STANCE,
    TOPIC,
)

REAL_STAGES = (COLLECTION, SECURITY, CLASSIFICATION)
STILL_STUBBED = (SENTIMENT, STANCE, AGGREGATION)


def test_every_stage_has_an_agent_either_way():
    for live in (False, True):
        assert build_default_registry(live=live).missing(PIPELINE_ORDER) == []


def test_stub_wiring_uses_stubs_everywhere():
    registry = build_default_registry(live=False)
    assert all(isinstance(registry.get(s), StubAgent) for s in PIPELINE_ORDER)


def test_live_wiring_uses_the_real_agents_where_they_exist():
    registry = build_default_registry(live=True)
    assert not any(isinstance(registry.get(s), StubAgent) for s in REAL_STAGES)


def test_stages_with_no_implementation_stay_stubbed_even_when_live():
    """
    None of these has an agent the pipeline can call. Asking for live
    agents must not quietly register something for them.
    """
    registry = build_default_registry(live=True)
    assert all(isinstance(registry.get(s), StubAgent) for s in STILL_STUBBED)


def test_building_the_live_registry_does_not_load_the_topic_model():
    """
    The topic module imports BERTopic and its ~2GB ML stack. Only running
    the stage may load it, or every live run, test and dev server start
    would pay for it, and fail outright wherever it is not installed.

    A fresh interpreter, because this process imported agents.adapters
    when the module loaded, so an eager import there has already run.
    """
    check = (
        "import sys\n"
        "from orchestrator.registry import build_default_registry\n"
        "build_default_registry(live=True)\n"
        "assert 'agents.topic.topic_model' not in sys.modules\n"
    )
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "-c", check], cwd=backend, check=True)


# --- topic: real only where it can run ---------------------------------
@pytest.fixture
def topic_models(monkeypatch, tmp_path):
    """An empty saved-models folder, standing in for agents/topic/models/."""
    monkeypatch.setattr("orchestrator.registry.TOPIC_MODELS", tmp_path)
    return tmp_path


def bertopic_installed(monkeypatch, installed):
    """Make BERTopic look installed or not, whatever this machine has."""
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, package=None: (
        (object() if installed else None) if name == "bertopic" else real(name, package)))


def test_topic_stays_stubbed_where_no_model_has_been_restored(monkeypatch, topic_models):
    """
    Without the model file the stage fails on every run, and every run
    ends completed_with_errors.
    """
    bertopic_installed(monkeypatch, True)
    assert isinstance(build_default_registry(live=True).get(TOPIC), StubAgent)


def test_topic_stays_stubbed_where_bertopic_is_not_installed(monkeypatch, topic_models):
    bertopic_installed(monkeypatch, False)
    (topic_models / "provisional_topic_model_v2.pkl").write_bytes(b"saved model")
    assert isinstance(build_default_registry(live=True).get(TOPIC), StubAgent)


def test_topic_runs_where_bertopic_and_a_saved_model_are_present(monkeypatch, topic_models):
    bertopic_installed(monkeypatch, True)
    (topic_models / "provisional_topic_model_v2.pkl").write_bytes(b"saved model")
    assert isinstance(build_default_registry(live=True).get(TOPIC), TopicAgent)


def test_a_git_lfs_pointer_is_not_mistaken_for_the_model(monkeypatch, topic_models, caplog):
    """
    The model is stored with Git LFS. Pulling without Git LFS leaves this
    small pointer file where the model should be; taking it for the model
    would fail the stage on every run with a checksum error.
    """
    bertopic_installed(monkeypatch, True)
    (topic_models / "provisional_topic_model_v2.pkl").write_bytes(
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:679406f32ccf370459691c43f4337331f909aa79d0dee5152ce7bf61ec84e1b0\n"
        b"size 441497055\n"
    )
    with caplog.at_level("WARNING", logger="orchestrator.registry"):
        registry = build_default_registry(live=True)
    assert isinstance(registry.get(TOPIC), StubAgent)
    assert "git lfs pull" in caplog.text


def test_sentiment_keeps_its_fallback():
    assert build_default_registry(live=True).get_fallback(SENTIMENT) is not None


def test_collection_options_reach_the_collection_agent():
    agent = build_default_registry(live=True, backlog=True, backlog_limit=7).get(COLLECTION)
    assert isinstance(agent, CollectionAgent)
    assert agent.backlog is True and agent.backlog_limit == 7


def test_the_environment_decides_when_live_is_not_given(monkeypatch):
    monkeypatch.setattr("agents.supabase_client.is_configured", lambda: False)
    assert isinstance(build_default_registry().get(COLLECTION), StubAgent)

    monkeypatch.setattr("agents.supabase_client.is_configured", lambda: True)
    assert not isinstance(build_default_registry().get(COLLECTION), StubAgent)


def test_the_llm_classifier_leads_when_it_has_credentials(monkeypatch):
    monkeypatch.setenv("TRUSSED_API_KEY", "sk-a-real-looking-key")
    monkeypatch.setenv("TRUSSED_BASE_URL", "https://trussed.example/chat/completions")
    registry = build_default_registry(live=True)
    primary, fallback = registry.get(CLASSIFICATION), registry.get_fallback(CLASSIFICATION)

    assert isinstance(primary, ClassificationAgent) and primary.classifier == "luna"
    assert isinstance(fallback, ClassificationAgent) and fallback.classifier == "baseline"


@pytest.mark.parametrize("key", ["your-trussed-api-key", "YOUR_KEY_HERE", "<your key>", "changeme", "", "   "])
def test_a_placeholder_key_does_not_count_as_configured(monkeypatch, key):
    """
    A .env copied from .env.example carries a placeholder. Treating it
    as real makes the LLM classifier the primary agent, so every run
    burns its retries on a 401 before falling back.
    """
    monkeypatch.setenv("TRUSSED_API_KEY", key)
    monkeypatch.setenv("TRUSSED_BASE_URL", "https://trussed.example/chat/completions")

    assert _luna_configured() is False
    registry = build_default_registry(live=True)
    primary = registry.get(CLASSIFICATION)
    assert isinstance(primary, ClassificationAgent) and primary.classifier == "baseline"
    assert registry.get_fallback(CLASSIFICATION) is None


def test_a_missing_base_url_also_means_not_configured(monkeypatch):
    monkeypatch.setenv("TRUSSED_API_KEY", "sk-a-real-looking-key")
    monkeypatch.delenv("TRUSSED_BASE_URL", raising=False)
    assert _luna_configured() is False


# --- placeholder credentials ------------------------------------------
@pytest.mark.parametrize("value", [
    None, "", "   ",
    "your-newsapi-key", "YOUR_KEY_HERE", "<paste key here>",
    "changeme", "replace-me", "xxxxx",
])
def test_unfilled_example_values_read_as_missing(value):
    from agents.config import is_placeholder

    assert is_placeholder(value) is True


@pytest.mark.parametrize("value", [
    "sb_secret_abc123", "sk-proj-abc", "d41d8cd98f00b204",
    # A real key is not discarded just because it contains one of the words.
    "abc-your-key-suffix", "keyxxx",
])
def test_real_looking_values_are_kept(value):
    from agents.config import is_placeholder

    assert is_placeholder(value) is False


def test_a_placeholder_news_key_skips_the_source_without_calling_it(monkeypatch, capsys):
    """
    Five 401s a second apart is what a copied .env used to buy. The
    fetcher should skip the source the same way it does with no key.
    """
    from agents.collection import fetchers

    monkeypatch.setenv("NEWS_API_KEY", "your-newsapi-key-here")

    def fail(*args, **kwargs):
        raise AssertionError("no request should be made with a placeholder key")

    monkeypatch.setattr(fetchers.requests, "get", fail)
    assert fetchers.fetch_from_newsapi() == []
    assert "NEWS_API_KEY not set" in capsys.readouterr().out


def test_a_dead_source_does_not_take_the_others_down(monkeypatch):
    """fetch_all returns partial results, as collection/README.md 4.1 says."""
    from agents.collection import fetchers

    def boom():
        raise ConnectionError("feed unreachable")

    monkeypatch.setitem(fetchers.SOURCES, "newsapi", boom)
    monkeypatch.setitem(fetchers.SOURCES, "gnews", lambda: [{"url": "https://x/1"}])
    monkeypatch.setitem(fetchers.SOURCES, "rss", lambda: [{"url": "https://x/2"}])

    assert len(fetchers.fetch_all()) == 2
