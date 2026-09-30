"""
SupabaseRunStore against a fake client.

The fake mimics the part of supabase-py's query builder the store uses
(table/insert/update/select/eq/order/limit/execute). This checks the
store's own logic — row mapping, timestamp handling, column checks — but
NOT the real Supabase API. It still needs one real run once the
pipeline tables exist.
"""
from datetime import timezone
from types import SimpleNamespace

import pytest

from helpers import failing, stages_by_name
from orchestrator.stages import PIPELINE_ORDER, TOPIC, RunStatus, StageStatus
from orchestrator.supabase_store import SupabaseRunStore, parse_ts


class FakeQuery:
    def __init__(self, tables, name):
        self.rows: list[dict] = tables.setdefault(name, [])
        self.op, self.filters = None, []
        self.payload: dict = {}
        self.sort, self.max_rows = None, None

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, fields):
        self.op, self.payload = "update", fields
        return self

    def select(self, columns):
        self.op = "select"
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column, desc=False):
        self.sort = (column, desc)
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def execute(self):
        matches = [r for r in self.rows if all(r.get(c) == v for c, v in self.filters)]
        if self.op == "insert":
            row = dict(self.payload, id=len(self.rows) + 1)
            self.rows.append(row)
            return SimpleNamespace(data=[dict(row)])
        if self.op == "update":
            for row in matches:
                row.update(self.payload)
            return SimpleNamespace(data=[dict(r) for r in matches])
        if self.sort:
            column, desc = self.sort
            matches = sorted(matches, key=lambda r: r[column], reverse=desc)
        if self.max_rows is not None:
            matches = matches[: self.max_rows]
        return SimpleNamespace(data=[dict(r) for r in matches])


class FakeClient:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        return FakeQuery(self.tables, name)


def test_full_pipeline_run_through_the_supabase_store(make_coordinator):
    client = FakeClient()
    coordinator = make_coordinator(store=SupabaseRunStore(client))
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED
    stages = stages_by_name(coordinator, run.id)
    assert list(stages) == list(PIPELINE_ORDER)
    assert all(s.status == StageStatus.SUCCEEDED for s in stages.values())
    # Rows were written as JSON-safe values, the way Supabase expects them.
    stored_run = client.tables["pipeline_runs"][0]
    assert isinstance(stored_run["started_at"], str) and isinstance(stored_run["finished_at"], str)


def test_partial_failure_is_recorded_in_the_tables(make_coordinator):
    client = FakeClient()
    coordinator = make_coordinator(store=SupabaseRunStore(client), agents={TOPIC: failing("topic")})
    run = coordinator.run()

    assert run.status == RunStatus.COMPLETED_WITH_ERRORS
    topic_row = next(r for r in client.tables["pipeline_stage_runs"] if r["stage_name"] == TOPIC)
    assert topic_row["status"] == StageStatus.FAILED
    assert "simulated failure" in topic_row["error_detail"]


def test_list_runs_newest_first():
    store = SupabaseRunStore(FakeClient())
    for _ in range(3):
        store.create_run("manual")
    assert [r.id for r in store.list_runs(limit=2)] == [3, 2]


def test_unknown_columns_are_rejected():
    store = SupabaseRunStore(FakeClient())
    run = store.create_run("manual")
    with pytest.raises(ValueError, match="statuss"):
        store.update_run(run.id, statuss="completed")


@pytest.mark.parametrize("text, microsecond", [
    ("2026-09-14T00:10:00.12Z", 120000),           # 'Z' suffix, short fraction
    ("2026-09-14T00:10:00.123456+00:00", 123456),
    ("2026-09-14 00:10:00+00:00", 0),              # space instead of 'T'
])
def test_timestamps_from_supabase_parse_on_older_python(text, microsecond):
    parsed = parse_ts(text)
    assert parsed is not None
    assert parsed.microsecond == microsecond
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_from_env_explains_missing_settings(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        SupabaseRunStore.from_env()
