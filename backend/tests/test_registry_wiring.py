"""
Which agent the registry picks for each stage.

The choice depends on the environment, which makes it exactly the kind
of thing that silently goes wrong: a placeholder key that reads as
'configured', or a test suite that behaves differently on the one
machine that happens to have a .env.
"""
import pytest

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
STILL_STUBBED = (SENTIMENT, TOPIC, STANCE, AGGREGATION)


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
    sentiment and stance have no implementation on any branch, and the
    topic model needs ~2GB of ML libraries. Asking for live agents must
    not quietly register something for them.
    """
    registry = build_default_registry(live=True)
    assert all(isinstance(registry.get(s), StubAgent) for s in STILL_STUBBED)


def test_sentiment_keeps_its_fallback():
    assert build_default_registry(live=True).get_fallback(SENTIMENT) is not None


def test_collection_options_reach_the_collection_agent():
    agent = build_default_registry(live=True, backlog=True, backlog_limit=7).get(COLLECTION)
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

    assert registry.get(CLASSIFICATION).classifier == "luna"
    assert registry.get_fallback(CLASSIFICATION).classifier == "baseline"


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
    assert registry.get(CLASSIFICATION).classifier == "baseline"
    assert registry.get_fallback(CLASSIFICATION) is None


def test_a_missing_base_url_also_means_not_configured(monkeypatch):
    monkeypatch.setenv("TRUSSED_API_KEY", "sk-a-real-looking-key")
    monkeypatch.delenv("TRUSSED_BASE_URL", raising=False)
    assert _luna_configured() is False
