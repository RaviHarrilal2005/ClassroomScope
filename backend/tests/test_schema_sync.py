"""
Keeps docs/pipeline_tables.sql and the orchestrator code in sync.

If someone renames a column or adds a status in one place but not the
other, this fails — before it becomes a confusing error against the
real database.
"""
import os
import re
from dataclasses import fields

import pytest

from orchestrator.models import RunRecord, StageRecord
from orchestrator.stages import PIPELINE_ORDER, TRIGGER_TYPES, RunStatus, StageStatus

SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "pipeline_tables.sql")


@pytest.fixture(scope="module")
def sql():
    with open(SQL_PATH, encoding="utf-8") as f:
        return f.read()


def table(sql, name):
    match = re.search(rf"create table if not exists public\.{name} \((.*?)\n\);", sql, re.S)
    assert match, f"table {name} not found in {SQL_PATH}"
    return match.group(1)


def columns(block):
    return set(re.findall(r"^\s{2}(\w+)\s+(?:bigint|text|timestamptz|integer)\b", block, re.M))


def allowed_values(block, column):
    match = re.search(rf"\b{column}\b[^,]*?check \({column} in \((.*?)\)\)", block, re.S)
    assert match, f"no check constraint for {column}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_pipeline_runs_columns_match_run_record(sql):
    assert columns(table(sql, "pipeline_runs")) == {f.name for f in fields(RunRecord)}


def test_pipeline_stage_runs_columns_match_stage_record(sql):
    assert columns(table(sql, "pipeline_stage_runs")) == {f.name for f in fields(StageRecord)}


def test_allowed_values_match_the_code(sql):
    runs, stages = table(sql, "pipeline_runs"), table(sql, "pipeline_stage_runs")
    run_statuses = {RunStatus.RUNNING, RunStatus.COMPLETED, RunStatus.COMPLETED_WITH_ERRORS, RunStatus.FAILED}
    stage_statuses = {StageStatus.PENDING, StageStatus.RUNNING, StageStatus.SUCCEEDED,
                      StageStatus.FAILED, StageStatus.SKIPPED}

    assert allowed_values(runs, "trigger_type") == set(TRIGGER_TYPES)
    assert allowed_values(runs, "status") == run_statuses
    assert allowed_values(stages, "stage_name") == set(PIPELINE_ORDER)
    assert allowed_values(stages, "status") == stage_statuses
