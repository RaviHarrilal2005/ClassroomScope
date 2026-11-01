"""Offline discovery contracts without loading ML runtimes or a database."""
import ast
import hashlib
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import pandas as pd


def functions(out):
    source = Path(__file__).with_name("train_auto.py")
    tree = ast.parse(source.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    scope = dict(Path=Path, pd=pd, json=json, hashlib=hashlib, MODELS_DIR=out,
                 VERSION_NAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*"),
                 MIN_ARTICLES=10, EMBEDDING_MODEL="test", UMAP_SETTINGS={}, DOMAIN_STOP_WORDS=set(),
                 SNAPSHOT_COLUMNS=("id", "content_hash", "clean_content", "is_relevant", "llm_relevant", "processing_status"))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)
    scope.update(now=lambda: "test", environment=lambda: {}, eligible_articles=lambda x: x)
    return scope


class DiscoveryTests(unittest.TestCase):
    def test_candidate_exports_and_replay(self):
        with TemporaryDirectory() as folder:
            scope = functions(Path(folder))
            articles = pd.DataFrame([dict(id=i, content_hash=str(i), clean_content=f"Text {i}",
                                        is_relevant=True, llm_relevant=True, processing_status="success")
                                     for i in range(10)])
            model = Mock()
            model.embedding_model = [Mock()]
            model.embedding_model[0].auto_model.config._commit_hash = "revision"
            model.fit_transform.return_value = ([-1] + [0] * 4 + [1] * 5, None)
            model.get_topic.return_value = [("integrity", 1)]
            model.get_topic_info.return_value = pd.DataFrame({"Topic": [-1, 0, 1], "Count": [1, 4, 5]})
            model.save.side_effect = lambda path, **kw: Path(path).write_bytes(b"candidate")
            builder = Mock(return_value=model)
            scope.update(build_model=builder, load_articles=lambda: articles)
            manifest = scope["train"]("candidate", topic_count=2)
            builder.assert_called_once_with(10, 2)
            self.assertEqual(manifest["topics"], 2)
            self.assertEqual(manifest["unassigned"], 1)
            self.assertIn("Unassigned (1 articles)", (Path(folder) / "candidate/review.md").read_text())
            snapshot = Path(folder) / "candidate/articles.json"
            self.assertEqual(len(scope["read_snapshot"](snapshot)), 10)
            with self.assertRaises(FileExistsError):
                scope["train"]("candidate")
            data = json.loads(snapshot.read_text())
            data["records"][0]["clean_content"] = "tampered"
            snapshot.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "checksum"):
                scope["read_snapshot"](snapshot)
            with self.assertRaisesRegex(ValueError, "cannot exceed"):
                scope["train"]("too-many", topic_count=11)
            self.assertEqual(json.loads((Path(folder) / "too-many/training.json").read_text())["status"], "failed")

    def test_invalid_counts_create_no_files(self):
        with TemporaryDirectory() as folder:
            scope = functions(Path(folder))
            for count in [0, 1, -1, True, 2.5]:
                with self.subTest(count=count), self.assertRaisesRegex(ValueError, "topic-count"):
                    scope["train"]("invalid", topic_count=count)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
