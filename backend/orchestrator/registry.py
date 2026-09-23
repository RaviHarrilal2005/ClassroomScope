"""
Maps each stage name to the agent that runs it (and an optional fallback).

This is the one place that changes when a teammate's real agent is
ready — swap the stub for the real class in build_default_registry().
The coordinator never imports specific agents, so adding or replacing
an agent doesn't touch the sequencing code.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from . import agents
from .agents import Agent
from .stages import AGGREGATION, ANALYSIS_STAGES, COLLECTION, SECURITY, SENTIMENT


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


def build_default_registry() -> AgentRegistry:
    """
    Current wiring: every stage is a stub until its owner's agent is ready.

    To plug in a real agent, replace its line, e.g.:
        registry.register(SENTIMENT, SentimentAgent(),
                          fallback=LexiconSentimentAgent())
    """
    registry = AgentRegistry()
    registry.register(COLLECTION, agents.stub_collection())    # TODO: real collection agent
    registry.register(SECURITY, agents.stub_security())        # TODO: real screening agent
    for stage in ANALYSIS_STAGES:                              # TODO: real analysis agents
        fallback = agents.stub_fallback(stage) if stage == SENTIMENT else None
        registry.register(stage, agents.stub_analysis(stage), fallback=fallback)
    registry.register(AGGREGATION, agents.stub_aggregation())  # TODO: real results aggregator
    return registry
