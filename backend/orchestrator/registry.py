"""
Maps each stage name to the agent that runs it (and an optional fallback).

This is the one place that changes when a teammate's real agent is
ready — swap the stub for the real class in build_default_registry().
The coordinator never imports specific agents, so adding or replacing
an agent doesn't touch the sequencing code.

The real agents live in backend/agents/; the Agent subclasses the
coordinator calls are in agents/adapters.py. They are imported inside
build_default_registry() rather than at module scope, so importing this
module never reaches for Supabase credentials.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Optional

from . import agents
from .agents import Agent
from .stages import (
    AGGREGATION,
    CLASSIFICATION,
    COLLECTION,
    SECURITY,
    SENTIMENT,
    STANCE,
    TOPIC,
)

logger = logging.getLogger(__name__)


class AgentRegistry:
    def __init__(self) -> None:
        self._primary: Dict[str, Agent] = {}
        self._fallback: Dict[str, Agent] = {}

    def register(self, stage: str, agent: Agent, fallback: Optional[Agent] = None) -> None:
        self._primary[stage] = agent
        if fallback is not None:
            self._fallback[stage] = fallback
        else:
            self._fallback.pop(stage, None)

    def get(self, stage: str) -> Agent:
        try:
            return self._primary[stage]
        except KeyError:
            raise KeyError(f"No agent registered for stage '{stage}'") from None

    def get_fallback(self, stage: str) -> Optional[Agent]:
        return self._fallback.get(stage)

    def missing(self, stages: Iterable[str]) -> List[str]:
        return [s for s in stages if s not in self._primary]


def build_default_registry(live: Optional[bool] = None, **collection_options) -> AgentRegistry:
    """
    Which agent runs each stage.

    live=True  use the team's real agents where they exist. They read and
               write Supabase, so this needs credentials.
    live=False stubs everywhere. No database, no network.
    live=None  (default) decide from the environment: real agents when
               Supabase is configured, stubs otherwise. That keeps
               `python run_pipeline.py` and the tests working on a
               machine with no .env, while a configured deployment gets
               the real pipeline without a code change.

    Stages with no implementation on any branch stay stubbed whatever
    `live` says -- see agents/adapters.py for which is which.

    collection_options are passed to CollectionAgent (backlog=True,
    preprocess_limit=..., sources=[...]).
    """
    registry = AgentRegistry()

    if live is None:
        from agents.supabase_client import is_configured

        live = is_configured()

    if live:
        from agents.adapters import ClassificationAgent, CollectionAgent, SecurityAgent

        logger.info("Registry: real agents for collection, security and classification")
        registry.register(COLLECTION, CollectionAgent(**collection_options))
        registry.register(SECURITY, SecurityAgent())
        # The LLM classifier is better but needs a reachable endpoint, so
        # it runs as primary only when it is configured, with the keyword
        # scorer behind it. Without credentials the keyword scorer is the
        # primary and there is nothing to fall back from.
        if _luna_configured():
            registry.register(CLASSIFICATION, ClassificationAgent("luna"),
                              fallback=ClassificationAgent("baseline"))
        else:
            logger.info("Registry: TRUSSED_API_KEY not set, using the keyword classifier")
            registry.register(CLASSIFICATION, ClassificationAgent("baseline"))
    else:
        logger.info("Registry: stub agents (Supabase not configured)")
        registry.register(COLLECTION, agents.stub_collection())
        registry.register(SECURITY, agents.stub_security())
        registry.register(CLASSIFICATION, agents.stub_analysis(CLASSIFICATION))

    # No implementation on any branch yet.
    registry.register(SENTIMENT, agents.stub_analysis(SENTIMENT),
                      fallback=agents.stub_fallback(SENTIMENT))
    registry.register(STANCE, agents.stub_analysis(STANCE))
    # agents/topic/topic_model.py runs standalone but pulls in ~2GB of ML
    # libraries, so the stage is stubbed on purpose. See the docs.
    registry.register(TOPIC, agents.stub_analysis(TOPIC))
    registry.register(AGGREGATION, agents.stub_aggregation())
    return registry


def _luna_configured() -> bool:
    """
    Whether the LLM classifier has real credentials.

    A .env copied from .env.example has TRUSSED_API_KEY set to a
    placeholder. Treating that as configured makes the LLM classifier
    the primary agent, so every run burns its retries on a 401 before
    falling back to the keyword scorer. A placeholder means unset.
    """
    from agents.config import is_placeholder

    return not is_placeholder(os.environ.get("TRUSSED_API_KEY")) and bool(
        (os.environ.get("TRUSSED_BASE_URL") or "").strip()
    )
