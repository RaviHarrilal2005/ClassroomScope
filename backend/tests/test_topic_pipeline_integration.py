"""Coordinator -> real topic logic -> persistence, without ML or network."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import numpy as np
import pandas as pd

from orchestrator import InMemoryRunStore, PipelineCoordinator, build_default_registry
from orchestrator.agents import StubAgent
from orchestrator.stages import TOPIC, RunStatus, StageStatus


class Query:
    def __init__(self, database, table):
        self.database, self.table = database, table
        self.filters, self.ids, self.window, self.records = [], None, None, None

    def select(self, columns):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        self.ids = set(values)
        self.database.requested_ids.append(list(values))
        return self

    def order(self, field):
        return self

    def range(self, first, last):
        self.window = (first, last + 1)
        return self

    def upsert(self, records, **kwargs):
        assert kwargs == {"on_conflict": "article_id", "ignore_duplicates": True,
                          "returning": "representation"}
        self.records = records
        return self

    def execute(self):
        if self.records is not None:
            inserted = []
            for row in self.records:
                if row["article_id"] not in self.database.saved:
                    self.database.saved[row["article_id"]] = row
                    inserted.append(row)
            return SimpleNamespace(data=inserted)
        rows = [r for r in self.database.articles
                if (self.ids is None or r["id"] in self.ids)
                and all(r.get(k) == v for k, v in self.filters)]
        return SimpleNamespace(data=rows[slice(*self.window)] if self.window else rows)


def test_pipeline_checks_only_approved_eligible_articles_and_saves_final_topics():
    # Load production definitions without importing BERTopic's heavyweight stack.
    source = Path(__file__).parents[1] / "agents/topic/topic_model.py"
    tree = ast.parse(source.read_text())
    definitions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                   or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                       and t.id == "TOPIC_RESULT_COLUMNS" for t in n.targets))]
    import json
    scope = {"pd": pd, "json": json, "Path": Path}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), scope)
    base = {"is_relevant": True, "llm_relevant": True, "processing_status": "success"}
    articles = [dict(base, id=i, content_hash=str(i), clean_content=text)
                for i, text in [(1, "model assigned"), (2, "clear fallback"),
                                (3, "ambiguous"), (4, "not security approved"),
                                (5, "not relevant"), (6, " ")]]
    articles[4]["is_relevant"] = False
    old = {"article_id": 1, "topic_id": 7, "topic": "Preserved old result"}
    database = SimpleNamespace(articles=articles, saved={1: dict(old)}, requested_ids=[])
    database.table = lambda table: Query(database, table)
    model = Mock()
    model.article_embedding_strategy = "truncate-v1"
    model.get_topic_info.return_value = pd.DataFrame({"Topic": [-1, 2, 7]})
    model.get_topics.return_value = {-1: [], 2: [], 7: []}
    model.topic_embeddings_ = np.array([[0, -1], [1, 0], [0, 1]])
    model.transform.side_effect = [([2], None), ([-1], None), ([-1], None)]
    model.embedding_model.embed_documents.side_effect = [np.array([[0, 1]]), np.array([[1, 1]])]
    model.get_topic.return_value = [("education", 1)]
    scope.update(get_database=lambda: database, DEFAULT_MODEL_PATH=Path("model.pkl"),
                 BERTopic=SimpleNamespace(load=lambda path: model),
                 use_installed_umap_functions=lambda model: None,
                 get_model_registration=lambda path: {
                     "version": "test-v1", "mapping_version": "test-mapping-v1", "labels": {"2": "Policy", "7": "Literacy"},
                     "topic_mapping": {"2": "T002", "7": "T005"}})
    output = {}
    inner = scope["TopicAgent"]()

    def run_topic(ctx):
        result = inner.run(ctx)
        output.update(result)
        return result

    registry = build_default_registry(live=False)
    registry.register("collection", StubAgent("collection", output={"article_ids": list(range(1, 7))}))
    registry.register("security", StubAgent("security", output={"approved_ids": [1, 2, 3, 5, 6]}))
    registry.register(TOPIC, StubAgent("topic_integration", output=run_topic))
    coordinator = PipelineCoordinator(registry, InMemoryRunStore(), sleep=lambda delay: None)
    run = coordinator.run()
    assert run.status == RunStatus.COMPLETED
    assert next(s for s in coordinator.store.list_stages(run.id) if s.stage_name == TOPIC).status == StageStatus.SUCCEEDED
    assert database.requested_ids[0] == [1, 2, 3, 5, 6]
    assert model.transform.call_args_list == [call([text]) for text in ["model assigned", "clear fallback", "ambiguous"]]
    assert model.embedding_model.embed_documents.call_args_list == [call([text], verbose=False) for text in ["clear fallback", "ambiguous"]]
    assert set(database.saved) == {1, 2, 3}
    assert database.saved[1] == old
    assert database.saved[2]["topic"] == "Unassigned"
    assert database.saved[2]["stable_topic_id"] is None
    assert database.saved[2]["suggested_topic"] == "Literacy"
    assert database.saved[2]["original_topic_id"] == -1
    assert database.saved[2]["assignment_method"] == "bertopic-single-document-v1"
    assert database.saved[2]["suggestion_method"] == "topic-cosine-0.85-gap-0.03-review-only-v3"
    assert database.saved[3]["topic_id"] == -1
    assert database.saved[2]["unassigned_reason"] == "uncertain_fit"
    assert database.saved[3]["unassigned_reason"] == "uncertain_fit"
    assert database.saved[2]["mapping_version"] == "test-mapping-v1"
    assert "mapping_version" not in database.saved[1]  # Legacy row remains untouched.
    assert output == {"processed": 3, "assigned": 1, "unassigned": 2,
                      "inserted": 2, "preserved": 1, "article_ids": [1, 2, 3]}
