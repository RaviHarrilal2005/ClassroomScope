"""Offline contract tests, without loading ML runtimes or writing to Supabase."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

import pandas as pd


def functions():
    source = Path(__file__).with_name("topic_model.py")
    tree = ast.parse(source.read_text())
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    scope = {"pd": pd, "Path": Path, "json": json, "hashlib": hashlib,
             "TOPIC_RESULT_COLUMNS": ["article_id", "topic_id", "topic", "topic_keywords",
                                      "stable_topic_id", "model_version"]}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), scope)
    return scope


def test_inference_filters_and_supports_single_article():
    scope = functions()
    model = Mock()
    model.get_topic_info.return_value = pd.DataFrame({"Topic": [-1, 0]})
    model.transform.return_value = ([0], None)
    model.get_topic.return_value = [("assessment", 1)]
    scope.update(DEFAULT_MODEL_PATH=Path("model.pkl"), BERTopic=SimpleNamespace(load=Mock(return_value=model)),
                 get_model_registration=Mock(return_value={"version": "v1", "labels": {"0": "Integrity"},
                                                          "topic_mapping": {"0": "T004"}}))
    base = dict(id=1, content_hash="hash", clean_content="Article text", is_relevant=True,
                llm_relevant=True, processing_status="success")
    rows = [base, dict(base, id=2), dict(base, id=3, llm_relevant=False),
            dict(base, id=4, processing_status="failed"), dict(base, id=5, clean_content=" "),
            dict(base, id=6, is_relevant=False)]
    result = scope["analyze_topics"](pd.DataFrame(rows))
    assert result.article_id.tolist() == [1]
    assert result.stable_topic_id.tolist() == ["T004"]
    model.transform.assert_called_once_with(["Article text"])
    model.fit_transform.assert_not_called()


def test_save_preserves_rows_and_reports_actual_insertions():
    scope = functions()
    database = Mock()
    upsert = database.table.return_value.upsert
    upsert.return_value.execute.return_value.data = [{"article_id": 1}]
    scope["get_database"] = Mock(return_value=database)
    rows = pd.DataFrame({"article_id": [1, 2], "stable_topic_id": ["T001", None],
                         "optional": [1.0, float("nan")]})
    assert scope["save_topic_results"](rows) == 1
    records = upsert.call_args.args[0]
    assert records[1]["optional"] is None
    json.dumps(records, allow_nan=False)
    assert upsert.call_args.kwargs["ignore_duplicates"] is True
    assert scope["save_topic_results"](pd.DataFrame()) == 0


def check_missing_or_changed_model(tmp_path):
    scope = functions()
    model = tmp_path / "model.pkl"
    with unittest.TestCase().assertRaisesRegex(ValueError, "missing"):
        scope["get_model_registration"](model)
    model.write_bytes(b"original")
    catalog = tmp_path / "catalog.json"
    registration = {"sha256": hashlib.sha256(b"original").hexdigest(), "topic_mapping": {"0": "T001"}}
    catalog.write_text(json.dumps({"models": {model.name: registration}, "topics": {"T001": {}}}))
    scope["TOPIC_CATALOG_PATH"] = catalog
    assert scope["get_model_registration"](model) == registration
    model.write_bytes(b"replacement")
    with unittest.TestCase().assertRaisesRegex(ValueError, "changed"):
        scope["get_model_registration"](model)


def test_missing_or_changed_model_cannot_trigger_training():
    with TemporaryDirectory() as directory:
        check_missing_or_changed_model(Path(directory))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(test) for test in (
        test_inference_filters_and_supports_single_article,
        test_save_preserves_rows_and_reports_actual_insertions,
        test_missing_or_changed_model_cannot_trigger_training,
    ))
