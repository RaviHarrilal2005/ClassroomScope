"""C1-C2, only with --collect: one real collection run from RSS and GNews (never NewsAPI)."""
from types import SimpleNamespace

import pytest

from e2e import database
from e2e.results import describe_run
from e2e.settings import COLLECTION_TIMEOUT


@pytest.fixture(scope="module")
def collection_run(pytestconfig, environment) -> SimpleNamespace:
    if not pytestconfig.getoption("--collect"):
        pytest.skip("real collection runs only with --collect")
    from orchestrator import BackgroundRunner, PipelineCoordinator, build_default_registry
    from orchestrator.models import to_dict
    from orchestrator.supabase_store import SupabaseRunStore

    db = environment.client
    newest_before = database.max_id(db, "articles")
    coordinator = PipelineCoordinator(build_default_registry(live=True, sources=["rss", "gnews"]),
                                      SupabaseRunStore.from_env())
    runner = BackgroundRunner(coordinator)
    started = runner.start("manual")
    finished = runner.wait(timeout=COLLECTION_TIMEOUT)
    record = coordinator.store.get_run(started.id)
    run = to_dict(record) if record is not None else {"id": started.id, "status": "missing"}
    run["stages"] = [to_dict(s) for s in coordinator.store.list_stages(started.id)]
    return SimpleNamespace(run=run, finished=finished, new_ids=database.ids_above(db, "articles", newest_before))


def test_c1_a_real_collection_run_completes(collection_run, record_property):
    run = collection_run.run
    found = (f"{run['articles_collected']} new analysable article(s)" if run.get("articles_collected")
             else "nothing new to analyse")
    record_property("note", f"run #{run['id']}: {found}; article rows stored: {collection_run.new_ids or 'none'}")
    assert collection_run.finished, f"still running after {COLLECTION_TIMEOUT}s"
    assert run["status"] == "completed", describe_run(run)


def test_c2_every_reported_article_is_analysable_and_classified(collection_run, environment):
    db = environment.client
    analysable = database.analysable(db, set(collection_run.new_ids))
    assert len(analysable) == (collection_run.run.get("articles_collected") or 0)
    missing = analysable - database.articles_with_rows(db, "classification_results", analysable)
    assert not missing, f"no classification rows for articles {sorted(missing)}"
