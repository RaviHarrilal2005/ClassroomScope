"""
Edge cases that start mattering once real agents replace the stubs:
malformed output, duplicate articles, quarantines, and agents that
misbehave. Add this file to backend/tests/ when the first real agent
is plugged in.
"""
import pytest

from helpers import failing, stages_by_name
from orchestrator.agents import StubAgent
from orchestrator.stages import (
    AGGREGATION,
    ANALYSIS_STAGES,
    COLLECTION,
    SECURITY,
    SENTIMENT,
    TOPIC,
    RunStatus,
    StageStatus,
)


@pytest.mark.parametrize("bad_output", [["not", "a", "dict"], {"article_ids": "1,2"}])
def test_other_malformed_collection_output_counts_as_failure(make_coordinator, bad_output):
    coordinator = make_coordinator(agents={COLLECTION: StubAgent("c", output=lambda ctx: bad_output)})
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "ContractError" in stages_by_name(coordinator, run.id)[COLLECTION].error_detail


def test_stage_fails_when_primary_and_fallback_both_fail(make_coordinator):
    coordinator = make_coordinator(
        agents={SENTIMENT: failing("sentiment")},
        fallbacks={SENTIMENT: failing("sentiment_fallback")},
    )
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS
    sentiment = stages_by_name(coordinator, run.id)[SENTIMENT]
    assert sentiment.status == StageStatus.FAILED
    assert "also failed" in sentiment.error_detail


def test_long_error_messages_are_shortened(make_coordinator):
    class Noisy(StubAgent):
        def run(self, ctx):
            raise RuntimeError("x" * 2000)

    coordinator = make_coordinator(agents={TOPIC: Noisy("topic")})
    run = coordinator.run()

    assert len(stages_by_name(coordinator, run.id)[TOPIC].error_detail) <= 500


def test_one_agent_cannot_change_what_another_sees(make_coordinator):
    seen = {}

    def careless_sentiment(ctx):
        ctx.approved_ids.clear()   # a buggy agent emptying the list it was given
        return {}

    def observe(ctx):
        seen["ids"] = list(ctx.approved_ids)
        return {}

    agents = {
        SENTIMENT: StubAgent("sentiment", output=careless_sentiment),
        AGGREGATION: StubAgent("aggregation", output=observe),
    }
    run = make_coordinator(agents=agents).run()

    assert run.status == RunStatus.COMPLETED
    assert seen["ids"] == [1, 2, 3, 4, 5]   # aggregation still sees every approved article


def test_everything_quarantined_skips_analysis(make_coordinator):
    agents = {SECURITY: StubAgent("s", output=lambda ctx: {"approved_ids": [], "quarantined_ids": ctx.article_ids})}
    coordinator = make_coordinator(agents=agents)
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    assert "0 passed security screening" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert stages[SECURITY].status == StageStatus.SUCCEEDED
    assert all(stages[s].status == StageStatus.SKIPPED for s in (*ANALYSIS_STAGES, AGGREGATION))


def test_duplicate_article_ids_are_counted_once(make_coordinator):
    run = make_coordinator(agents={COLLECTION: StubAgent("c", output={"article_ids": [7, 7, 8]})}).run()
    assert run.articles_collected == 2


def test_aggregation_is_told_which_analysis_stages_finished(make_coordinator):
    received = {}

    def aggregate(ctx):
        received["stages"] = list(ctx.completed_analysis)
        return {}

    run = make_coordinator(agents={AGGREGATION: StubAgent("agg", output=aggregate)}).run()

    assert run.status == RunStatus.COMPLETED
    assert received["stages"] == list(ANALYSIS_STAGES)
