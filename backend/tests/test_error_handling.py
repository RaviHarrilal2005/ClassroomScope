"""Error handling: retry with backoff, fail-closed security, fallback, partial results."""
import pytest
from helpers import failing, stages_by_name
from orchestrator import InMemoryRunStore
from orchestrator.agents import StubAgent
from orchestrator.stages import (
    AGGREGATION,
    ANALYSIS_STAGES,
    CLASSIFICATION,
    COLLECTION,
    COMMENT_SENTIMENT,
    PIPELINE_ORDER,
    SECURITY,
    SENTIMENT,
    STANCE,
    TOPIC,
    RunStatus,
    StageStatus,
)

# --- Collection: retry with backoff ----------------------------------------

def test_flaky_collection_is_retried_and_recovers(make_coordinator, sleeps):
    flaky = StubAgent("collection", output={"article_ids": [1, 2]}, fail_times=1)
    coordinator = make_coordinator(agents={COLLECTION: flaky})
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    collection = stages_by_name(coordinator, run.id)[COLLECTION]
    assert collection.status == StageStatus.SUCCEEDED
    assert collection.attempt == 2
    assert sleeps == [2.0]   # waited once before the retry


def test_collection_that_keeps_failing_stops_the_run(make_coordinator, sleeps):
    coordinator = make_coordinator(agents={COLLECTION: failing("collection")})
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "Collection failed" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert stages[COLLECTION].status == StageStatus.FAILED
    assert stages[COLLECTION].attempt == 3
    assert "simulated failure" in stages[COLLECTION].error_detail
    assert all(stages[s].status == StageStatus.SKIPPED for s in PIPELINE_ORDER[1:])
    assert sleeps == [2.0, 4.0]   # backoff doubles between attempts


# --- Security fails closed -------------------------------------------------

def test_security_failure_skips_analysis(make_coordinator):
    coordinator = make_coordinator(agents={SECURITY: failing("security")})
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "Security screening failed" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert stages[SECURITY].status == StageStatus.FAILED
    assert all(stages[s].status == StageStatus.SKIPPED for s in (*ANALYSIS_STAGES, AGGREGATION))


def test_security_cannot_approve_articles_that_were_never_collected(make_coordinator):
    agents = {
        COLLECTION: StubAgent("c", output={"article_ids": [1, 2]}),
        SECURITY: StubAgent("s", output={"approved_ids": [1, 99]}),
    }
    coordinator = make_coordinator(agents=agents)
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    security = stages_by_name(coordinator, run.id)[SECURITY]
    assert "never collected: 99" in security.error_detail


# --- Agent contract check --------------------------------------------------

def test_collection_output_missing_article_ids_counts_as_failure(make_coordinator):
    coordinator = make_coordinator(agents={COLLECTION: StubAgent("c", output={"ids": [1, 2]})})
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "ContractError" in stages_by_name(coordinator, run.id)[COLLECTION].error_detail


# --- Analysis: independent agents, fallback, partial results ----------------

def test_one_analysis_failure_does_not_stop_the_others(make_coordinator):
    received = {}

    def aggregate(ctx):
        received["stages"] = list(ctx.completed_analysis)
        return {}

    agents = {TOPIC: failing("topic"), AGGREGATION: StubAgent("agg", output=aggregate)}
    coordinator = make_coordinator(agents=agents)
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS
    assert "Failed stage(s): topic" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert stages[TOPIC].status == StageStatus.FAILED
    others = [s for s in ANALYSIS_STAGES if s != TOPIC]
    for stage in (*others, AGGREGATION):
        assert stages[stage].status == StageStatus.SUCCEEDED
    assert received["stages"] == others


def test_sentiment_uses_fallback_when_primary_fails(make_coordinator):
    coordinator = make_coordinator(agents={SENTIMENT: failing("sentiment")})  # default fallback kept
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    sentiment = stages_by_name(coordinator, run.id)[SENTIMENT]
    assert sentiment.status == StageStatus.SUCCEEDED
    assert sentiment.attempt == 2
    assert "fallback 'sentiment_fallback_stub' was used" in sentiment.error_detail


def test_every_analysis_stage_failing_fails_the_run(make_coordinator):
    coordinator = make_coordinator(
        agents={stage: failing(stage) for stage in ANALYSIS_STAGES},
        fallbacks={SENTIMENT: None},
    )
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "Every analysis stage failed" in run.notes
    assert stages_by_name(coordinator, run.id)[AGGREGATION].status == StageStatus.SKIPPED


def test_aggregation_failure_keeps_the_analysis_results(make_coordinator):
    coordinator = make_coordinator(agents={AGGREGATION: failing("aggregation")})
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS
    assert "Failed stage(s): aggregation" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert all(stages[s].status == StageStatus.SUCCEEDED for s in ANALYSIS_STAGES)


# --- A run never gets stuck ------------------------------------------------

def test_coordinator_error_never_leaves_a_run_stuck(make_coordinator, monkeypatch):
    coordinator = make_coordinator()

    def crash(*args, **kwargs):
        raise RuntimeError("database connection lost")

    monkeypatch.setattr(coordinator, "_run_analysis", crash)
    run = coordinator.run()

    assert run.status == RunStatus.FAILED
    assert "Coordinator error" in run.notes and "database connection lost" in run.notes
    stages = stages_by_name(coordinator, run.id)
    assert not any(s.status in (StageStatus.PENDING, StageStatus.RUNNING) for s in stages.values())


def test_a_rejected_stage_row_fails_the_run_instead_of_leaving_it_running(make_coordinator):
    # Run #66: the database's stage-name check had no 'comment_sentiment' yet
    # (a missing migration), so start_run raised after creating six stage rows
    # and the run sat at 'running' with every stage 'pending'.
    store = InMemoryRunStore()
    create_stage = store.create_stage

    def reject_comment_sentiment(run_id, stage_name):
        if stage_name == COMMENT_SENTIMENT:
            raise RuntimeError("violates check constraint pipeline_stage_runs_stage_name_check")
        return create_stage(run_id, stage_name)

    store.create_stage = reject_comment_sentiment
    coordinator = make_coordinator(store=store)
    with pytest.raises(RuntimeError, match="check constraint"):
        coordinator.start_run()

    run = store.list_runs()[0]
    assert run.status == RunStatus.FAILED
    assert "stage rows" in run.notes and "check constraint" in run.notes
    assert all(s.status == StageStatus.SKIPPED for s in store.list_stages(run.id))
