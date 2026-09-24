"""Sequencing: stages run in the right order and pass the right IDs along."""
import threading

import pytest

from helpers import stages_by_name
from orchestrator import AgentRegistry, InMemoryRunStore, PipelineCoordinator
from orchestrator.agents import Output, OutputSource, StubAgent, stub_collection
from orchestrator.stages import (
    AGGREGATION,
    ANALYSIS_STAGES,
    COLLECTION,
    PIPELINE_ORDER,
    SECURITY,
    SENTIMENT,
    RunStatus,
    StageStatus,
)


def recording(stage, log, output: OutputSource):
    """Stub that notes when it ran, then returns `output` (dict or function)."""

    def run(ctx) -> Output:
        log.append(stage)
        return output(ctx) if callable(output) else output or {}

    return StubAgent(f"{stage}_recording", output=run)


def test_happy_path_every_stage_succeeds(make_coordinator):
    coordinator = make_coordinator()
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    assert run.finished_at is not None
    assert run.articles_collected == 5
    stages = stages_by_name(coordinator, run.id)
    assert list(stages) == list(PIPELINE_ORDER)
    assert all(s.status == StageStatus.SUCCEEDED for s in stages.values())
    assert all(s.attempt == 1 and s.error_detail is None for s in stages.values())


def test_stages_run_in_pipeline_order(make_coordinator):
    log = []
    agents = {
        COLLECTION: recording(COLLECTION, log, {"article_ids": [1, 2, 3]}),
        SECURITY: recording(SECURITY, log, lambda ctx: {"approved_ids": ctx.article_ids}),
        AGGREGATION: recording(AGGREGATION, log, {}),
    }
    for stage in ANALYSIS_STAGES:
        agents[stage] = recording(stage, log, {})

    make_coordinator(agents=agents).run()

    assert log[0] == COLLECTION
    assert log[1] == SECURITY
    assert sorted(log[2:6]) == sorted(ANALYSIS_STAGES)  # any order — they run in parallel
    assert log[6] == AGGREGATION


def test_analysis_agents_run_at_the_same_time(make_coordinator):
    # Each analysis agent waits at a barrier that only opens once all four
    # are waiting. If they ran one after another, the first would time out.
    barrier = threading.Barrier(len(ANALYSIS_STAGES), timeout=5)

    def meet(ctx):
        barrier.wait()
        return {"processed": len(ctx.approved_ids)}

    agents = {stage: StubAgent(stage, output=meet) for stage in ANALYSIS_STAGES}
    run = make_coordinator(agents=agents, fallbacks={SENTIMENT: None}).run()

    assert run.status == RunStatus.COMPLETED


def test_analysis_only_sees_articles_that_passed_security(make_coordinator):
    seen = {}

    def capture(stage):
        def run(ctx):
            seen[stage] = list(ctx.approved_ids)
            return {"processed": len(ctx.approved_ids)}
        return run

    agents = {
        COLLECTION: StubAgent("c", output={"article_ids": [1, 2, 3, 4, 5]}),
        SECURITY: StubAgent("s", output={"approved_ids": [1, 3], "quarantined_ids": [2, 4, 5]}),
    }
    agents.update({stage: StubAgent(stage, output=capture(stage)) for stage in ANALYSIS_STAGES})

    run = make_coordinator(agents=agents).run()

    assert seen == {stage: [1, 3] for stage in ANALYSIS_STAGES}
    assert run.notes == "Collected 5 article(s); 2 passed security screening."


def test_no_new_articles_ends_run_early(make_coordinator):
    coordinator = make_coordinator(agents={COLLECTION: StubAgent("c", output={"article_ids": []})})
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    assert run.articles_collected == 0
    assert run.notes == "No new articles were collected."
    stages = stages_by_name(coordinator, run.id)
    assert stages[COLLECTION].status == StageStatus.SUCCEEDED
    assert all(stages[s].status == StageStatus.SKIPPED for s in PIPELINE_ORDER[1:])


def test_missing_agent_is_caught_at_startup():
    registry = AgentRegistry()
    registry.register(COLLECTION, stub_collection())
    with pytest.raises(ValueError, match="security"):
        PipelineCoordinator(registry, InMemoryRunStore())
