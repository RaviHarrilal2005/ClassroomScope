"""Offline contract tests, without loading ML runtimes or writing to Supabase."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, call

import pandas as pd


def functions():
    source = Path(__file__).with_name("topic_model.py")
    tree = ast.parse(source.read_text())
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    definitions.insert(0, next(n for n in tree.body if isinstance(n, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == "TOPIC_RESULT_COLUMNS"
                                      for t in n.targets)))
    scope = {"pd": pd, "Path": Path, "json": json, "hashlib": hashlib,
             "TOPIC_RESULT_COLUMNS": ["article_id", "topic_id", "topic", "topic_keywords",
                                      "stable_topic_id", "model_version"]}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), scope)
    return scope


def test_inference_filters_and_supports_single_article():
    scope = functions()
    model = Mock()
    model.article_embedding_strategy = "truncate-v1"
    model.get_topic_info.return_value = pd.DataFrame({"Topic": [-1, 0]})
    model.transform.return_value = ([0], None)
    model.get_topic.return_value = [("assessment", 1)]
    repair = Mock()
    scope.update(DEFAULT_MODEL_PATH=Path("model.pkl"), BERTopic=SimpleNamespace(load=Mock(return_value=model)),
                 use_installed_umap_functions=repair,
                 get_model_registration=Mock(return_value={"version": "v1", "mapping_version": "test-mapping-v1", "labels": {"0": "Integrity"},
                                                          "topic_mapping": {"0": "T004"}}))
    base = dict(id=1, content_hash="hash", clean_content="Article text", is_relevant=True,
                llm_relevant=True, processing_status="success")
    rows = [base, dict(base, id=2), dict(base, id=3, llm_relevant=False),
            dict(base, id=4, processing_status="failed"), dict(base, id=5, clean_content=" "),
            dict(base, id=6, is_relevant=False)]
    result = scope["analyze_topics"](pd.DataFrame(rows))
    assert result.article_id.tolist() == [1]
    assert result.stable_topic_id.tolist() == ["T004"]
    assert result.mapping_version.tolist() == ["test-mapping-v1"]
    assert result.unassigned_reason.tolist() == [None]
    model.transform.assert_called_once_with(["Article text"])
    model.fit_transform.assert_not_called()
    repair.assert_called_once_with(model)
    model.article_embedding_strategy = "token-sections-weighted-mean-v1"
    with unittest.TestCase().assertRaisesRegex(ValueError, "strategy"):
        scope["analyze_topics"](pd.DataFrame([base]))


def test_loaded_model_uses_this_machines_umap_distance_functions():
    """
    The pickle carries copies of umap's numba distance functions compiled
    for the Python that trained it (3.12). On another Python version numba
    cannot compile them and transform fails: "IndexError: pop from empty list".
    """
    scope = functions()
    def cosine(): pass
    def cosine_grad(): pass
    def euclidean_grad(): pass
    umap_model = SimpleNamespace(_input_distance_func=SimpleNamespace(py_func=cosine),
                                 _inverse_distance_func=SimpleNamespace(py_func=cosine_grad),
                                 _output_distance_func=SimpleNamespace(py_func=euclidean_grad))
    installed = SimpleNamespace(cosine=object(), cosine_grad=object(), euclidean_grad=object())
    scope["use_installed_umap_functions"](SimpleNamespace(umap_model=umap_model), installed)
    assert umap_model._input_distance_func is installed.cosine
    assert umap_model._inverse_distance_func is installed.cosine_grad
    assert umap_model._output_distance_func is installed.euclidean_grad


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
    registration = {"sha256": hashlib.sha256(b"original").hexdigest(), "topic_mapping": {"0": "T001"}, "labels": {"0": "Student adoption"}}
    catalog.write_text(json.dumps({"models": {model.name: registration}, "topics": {"T001": {}}}))
    scope["TOPIC_CATALOG_PATH"] = catalog
    first = scope["get_model_registration"](model)
    assert first["sha256"] == registration["sha256"]
    assert first["mapping_version"].startswith("sha256:")
    assert scope["get_model_registration"](model)["mapping_version"] == first["mapping_version"]
    revised = json.loads(catalog.read_text())
    revised["topics"]["T001"]["description"] = "Student adoption only"
    catalog.write_text(json.dumps(revised))
    assert scope["get_model_registration"](model)["mapping_version"] != first["mapping_version"]
    model.write_bytes(b"replacement")
    with unittest.TestCase().assertRaisesRegex(ValueError, "changed"):
        scope["get_model_registration"](model)


def test_missing_or_changed_model_cannot_trigger_training():
    with TemporaryDirectory() as directory:
        check_missing_or_changed_model(Path(directory))


def test_second_check_preserves_assignments_and_rejects_weak_or_ambiguous_matches():
    import numpy as np
    scope = functions()
    model = Mock()
    # Noncontiguous IDs and an outlier vector verify row-to-topic alignment.
    model.get_topics.return_value = {-1: [], 2: [], 7: []}
    model.get_topic.return_value = [("education", 1)]
    model.topic_embeddings_ = np.array([[0, -1], [1, 0], [0, 1]])
    model.embedding_model.embed_documents.side_effect = [np.array([v]) for v in
        [[1, 0], [1, 1], [-1, -1], [0, 1]]]
    registration = {"labels": {"2": "Policy", "7": "Literacy"},
                    "topic_mapping": {"2": "T002", "7": "T005"}}
    result = pd.DataFrame({"article_id": range(5), "topic_id": [2, -1, -1, -1, -1],
                           "topic": ["Policy"] + ["Unassigned"] * 4,
                           "stable_topic_id": ["T002"] + [None] * 4,
                           "original_topic_id": [2, -1, -1, -1, -1],
                           "assignment_method": "bertopic"},
                          columns=scope["TOPIC_RESULT_COLUMNS"])
    output = scope["add_unassigned_suggestions"](
        result, ["assigned", "clear", "ambiguous", "weak", "literacy"], model, registration)
    assert output.topic_id.tolist() == [2, -1, -1, -1, -1]
    assert output.topic.tolist() == ["Policy", "Unassigned", "Unassigned", "Unassigned", "Unassigned"]
    assert output.original_topic_id.tolist() == [2, -1, -1, -1, -1]
    assert output.loc[1, "assignment_method"] == "bertopic"
    assert output.loc[1, "suggestion_method"] == "topic-cosine-0.85-gap-0.03-review-only-v3"
    assert pd.isna(output.loc[1, "topic_keywords"])
    assert pd.isna(output.loc[1, "stable_topic_id"])
    assert output.loc[0, "assignment_method"] == "bertopic"
    assert output.loc[1, "suggested_stable_topic_id"] == "T002"
    assert output.loc[4, "suggested_stable_topic_id"] == "T005"
    assert pd.isna(output.loc[2, "suggested_topic"])
    assert pd.isna(output.loc[3, "suggested_topic"])
    assert pd.isna(output.loc[0, "suggestion_method"])
    assert model.embedding_model.embed_documents.call_args_list == [
        call([text], verbose=False) for text in ["clear", "ambiguous", "weak", "literacy"]]
    assert scope["summarize_topic_results"](output) == {"processed": 5, "assigned": 1, "unassigned": 4}


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(test) for test in (
        test_inference_filters_and_supports_single_article,
        test_loaded_model_uses_this_machines_umap_distance_functions,
        test_save_preserves_rows_and_reports_actual_insertions,
        test_missing_or_changed_model_cannot_trigger_training,
        test_second_check_preserves_assignments_and_rejects_weak_or_ambiguous_matches,
    ))


def test_inference_is_independent_of_batch_and_order():
    scope=functions()
    model=Mock()
    model.article_embedding_strategy='truncate-v1'
    model.get_topic_info.return_value=pd.DataFrame({'Topic':[0,1]})
    # Mimic the observed dependency: batching would change every raw label.
    def predict(documents):
        return ([1]*len(documents) if len(documents)>1 else [0 if documents[0]=='alpha' else 1],None)
    model.transform.side_effect=predict
    model.get_topic.return_value=[('education',1)]
    scope.update(DEFAULT_MODEL_PATH=Path('model.pkl'),BERTopic=SimpleNamespace(load=lambda path:model),
                 use_installed_umap_functions=lambda model:None,
                 get_model_registration=lambda path:dict(version='test',labels={'0':'Learning','1':'Practice'},
                     topic_mapping={'0':'T001','1':'T003'}))
    base=dict(is_relevant=True,llm_relevant=True,processing_status='success')
    articles=pd.DataFrame([dict(base,id=1,content_hash='a',clean_content='alpha'),
                           dict(base,id=2,content_hash='b',clean_content='beta')])
    def run(frame):
        return scope['analyze_topics'](frame).set_index('article_id').stable_topic_id.to_dict()
    expected={1:'T001',2:'T003'}
    assert run(articles)==expected
    assert run(articles.iloc[::-1])==expected
    assert run(articles.iloc[:1])=={1:'T001'}
    assert all(len(args.args[0])==1 for args in model.transform.call_args_list)
