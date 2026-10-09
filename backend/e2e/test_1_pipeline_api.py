"""P1-P5: one real pipeline run through the API (the `api_run` fixture)."""
from datetime import datetime

from e2e import database
from e2e.results import describe_run
from orchestrator.stages import PIPELINE_ORDER

STUBS = ("sentiment", "stance", "aggregation")
ALL_SUCCEEDED = [(name, "succeeded") for name in PIPELINE_ORDER]


def test_p1_starting_a_run_returns_at_once(api_run, record_property):
    assert api_run.first.status_code == 202, api_run.first.text
    run = api_run.first.json()
    record_property("note", f"run #{run['id']}")
    assert run["status"] == "running"
    stages = {s["stage_name"]: s["status"] for s in run["stages"]}
    assert list(stages) == list(PIPELINE_ORDER)
    # The response lists the stages after the run's thread has started, so
    # collection may already be running; every later stage must be pending.
    assert stages.pop("collection") in ("pending", "running")
    assert set(stages.values()) == {"pending"}


def test_p2_the_run_completes_with_every_stage_succeeding(api_run, record_property):
    run = api_run.final
    assert run is not None and run["status"] == "completed", describe_run(run)
    assert [(s["stage_name"], s["status"]) for s in run["stages"]] == ALL_SUCCEEDED, describe_run(run)
    assert run["articles_collected"] == 5
    assert run["notes"] == "Collected 5 article(s); 5 passed security screening."
    took = datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["started_at"])
    record_property("note", f"run #{run['id']} took {took.total_seconds():.0f}s; "
                            f"stub stages: {', '.join(STUBS)}")


def test_p3_a_second_run_is_refused_while_one_is_active(api_run):
    assert api_run.second.status_code == 409, api_run.second.text
    assert api_run.second.json()["active_run_id"] == api_run.first.json()["id"]


def test_p4_the_run_list_shows_the_run_first(api_run):
    assert api_run.listing["runs"][0]["id"] == api_run.first.json()["id"]
    assert api_run.listing["active_run_id"] is None


def test_p5_the_database_holds_the_results(api_run, environment, record_property):
    db = environment.client
    run_id = api_run.first.json()["id"]
    row = database.run_row(db, run_id)
    assert row["status"] == "completed"
    assert [(s["stage_name"], s["status"]) for s in database.stage_rows(db, run_id)] == ALL_SUCCEEDED

    classified = database.classified_between(db, row["started_at"], row["finished_at"])
    record_property("note", f"articles {sorted(classified)}")
    assert len(classified) == 5, sorted(classified)
    assert database.analysable(db, classified) == classified
    missing = classified - database.articles_with_rows(db, "topic_results", classified)
    assert not missing, f"no topic_results row for articles {sorted(missing)}"
