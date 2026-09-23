import os
import sys

import pytest

# Make `orchestrator` and `app` importable when running `pytest` from backend/.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from orchestrator import InMemoryRunStore, PipelineCoordinator, build_default_registry  # noqa: E402



@pytest.fixture
def sleeps():
    """Backoff delays the coordinator asked for — recorded instead of actually waited."""
    return []


@pytest.fixture
def make_coordinator(sleeps):
    """
    Build a coordinator with the default stub agents, optionally overriding some.

        make_coordinator(agents={TOPIC: StubAgent("t", fail_times=-1)})
        make_coordinator(fallbacks={SENTIMENT: None})   # remove a fallback
    """

    def factory(agents=None, fallbacks=None, policies=None, store=None):
        registry = build_default_registry()
        agents, fallbacks = agents or {}, fallbacks or {}
        for stage in set(agents) | set(fallbacks):
            primary = agents.get(stage, registry.get(stage))
            fallback = fallbacks[stage] if stage in fallbacks else registry.get_fallback(stage)
            registry.register(stage, primary, fallback=fallback)
        return PipelineCoordinator(
            registry, store or InMemoryRunStore(), policies=policies, sleep=sleeps.append,
        )

    return factory
