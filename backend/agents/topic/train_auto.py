"""
Train a candidate topic model that chooses its own number of topics.

    python -m agents.topic.train_auto --version auto-v1        (from backend/)

The same pipeline that trained provisional-v2 (the training code in commit
fff48c2), except nr_topics=None: the clustering decides how many topics
there are. min_topic_size is a cluster-size setting, not a topic count.
Training records include an exact eligible-input snapshot for later replay.

A candidate is saved to models/<version>/ and goes no further. It is not
registered in topic_catalog.json, its topic numbers are not T001-T005, and
normal runs keep using the registered model. It reads eligible articles
from Supabase and writes nothing to the database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import pandas as pd

from .topic_model import eligible_articles, load_articles

MODELS_DIR = Path(__file__).resolve().parent / "models"

EMBEDDING_MODEL = "all-mpnet-base-v2"
UMAP_SETTINGS = {"n_neighbors": 8, "n_components": 5, "min_dist": 0.0, "metric": "cosine", "random_state": 42}
DOMAIN_STOP_WORDS = {
    "ai", "artificial", "intelligence", "education", "educational",
    "student", "students", "school", "schools", "teacher", "teachers",
    "said", "says", "say", "new", "use", "used", "using",
    "educators", "tools", "tool", "help", "systems", "generated",
    "technology", "information", "districts", "district", "automated", "support", "12",
}
# Fewer articles than this cannot support topic discovery.
MIN_ARTICLES = 10
# A plain folder name: no path separators, and nothing starting with a dot.
VERSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
# Recorded with each candidate. A pickle only loads cleanly where these
# match: provisional-v2, pickled on Python 3.12, needs a workaround on 3.13.
LIBRARIES = ("bertopic", "umap-learn", "hdbscan", "sentence-transformers", "numba", "numpy", "pandas", "scikit-learn", "torch", "transformers")


def build_model(min_topic_size, topic_count=None):
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer
    from umap import UMAP
    from sklearn.cluster import KMeans

    return BERTopic(
        embedding_model=SentenceTransformer(EMBEDDING_MODEL),
        vectorizer_model=CountVectorizer(
            stop_words=list(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS), ngram_range=(1, 1), min_df=1, max_df=1.0
        ),
        umap_model=UMAP(**UMAP_SETTINGS),
        min_topic_size=min_topic_size,
        nr_topics=None,
        hdbscan_model=KMeans(n_clusters=topic_count, random_state=42, n_init=10) if topic_count else None,
    )


def train(version, min_topic_size=10, snapshot_path=None, topic_count=None):
    """Train, then save the candidate to MODELS_DIR/<version>. Returns its manifest."""
    if not VERSION_NAME.fullmatch(version):
        raise ValueError(f"--version must be a plain folder name like auto-v1, not {version!r}")
    if isinstance(min_topic_size, bool) or not isinstance(min_topic_size, int) or min_topic_size < 2:
        raise ValueError("--min-topic-size must be at least 2")

    if topic_count is not None and (isinstance(topic_count, bool) or not isinstance(topic_count, int) or topic_count < 2):
        raise ValueError("--topic-count must be an integer of at least 2")

    out = MODELS_DIR / version
    out.mkdir(parents=True)  # FileExistsError: a candidate is never overwritten
    manifest = {
        "version": version,
        "status": "running",
        "started_at": now(),
        "note": "Candidate only: not registered in topic_catalog.json; topic numbers are not T001-T005.",
        "settings": {
            "embedding_model": EMBEDDING_MODEL,
            "nr_topics": None,
            "topic_count": topic_count,
            "clustering": "kmeans" if topic_count else "hdbscan",
            "min_topic_size": min_topic_size,
            "umap": UMAP_SETTINGS,
            "stop_words": sorted(DOMAIN_STOP_WORDS),
            "hdbscan_min_samples": None if topic_count else min_topic_size,
        },
        "environment": environment(),
    }
    write_manifest(out, manifest)
    try:
        articles = read_snapshot(snapshot_path) if snapshot_path else eligible_articles(load_articles())
        normalized = articles['clean_content'].map(lambda text: ' '.join(text.casefold().split()))
        duplicates = normalized.duplicated()
        manifest['normalized_text_duplicate_ids_removed'] = articles.loc[duplicates, 'id'].tolist()
        articles = articles.loc[~duplicates].copy()
        if len(articles) < MIN_ARTICLES:
            raise ValueError(f"Found {len(articles)} eligible article(s); training needs at least {MIN_ARTICLES}.")
        articles = articles.sort_values("id", kind="stable").reset_index(drop=True)
        snapshot = make_snapshot(articles)
        snapshot_file = out / "articles.json"
        snapshot_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.update(input_snapshot_sha256=sha256(snapshot_file), input_documents_sha256=snapshot["documents_sha256"],
                        article_ids=articles["id"].tolist(), input_source="snapshot" if snapshot_path else "database")
        write_manifest(out, manifest)

        if topic_count is not None and topic_count > len(articles):
            raise ValueError("--topic-count cannot exceed the number of eligible articles")
        model = build_model(min_topic_size, topic_count)
        encoder = model.embedding_model
        manifest["settings"]["resolved_embedding_revision"] = getattr(encoder[0].auto_model.config, "_commit_hash", None)
        write_manifest(out, manifest)
        documents = articles["clean_content"].tolist()
        topics, _ = model.fit_transform(documents)
        model.save(str(out / "model.pkl"), serialization="pickle")

        keywords = {t: "; ".join(w for w, _ in (model.get_topic(t) or [])) for t in set(topics) if t != -1}
        info = model.get_topic_info()
        pd.DataFrame({
            "topic_id": info["Topic"],
            "count": info["Count"],
            "keywords": [keywords.get(t, "") for t in info["Topic"]],
        }).to_csv(out / "topics.csv", index=False)
        pd.DataFrame({
            "article_id": articles["id"],
            "topic_id": topics,
            "topic_keywords": [keywords.get(t, "") for t in topics],
        }).to_csv(out / "assignments.csv", index=False)

        write_review(out, articles, topics, keywords)
        manifest.update(
            status="succeeded",
            articles=len(articles),
            topics=len(keywords),
            unassigned=int(sum(t == -1 for t in topics)),
            model_sha256=sha256(out / "model.pkl"),
        )
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest["finished_at"] = now()
        write_manifest(out, manifest)
    return manifest


def write_review(out, articles, topics, keywords):
    """Save deterministic samples, including outliers, without claiming accuracy."""
    rows = articles.assign(topic_id=topics)
    lines = ["# Candidate topic review", "",
             "Review samples for thematic fit, overlapping themes, duplicate coverage, and source quality.",
             "Samples are the first three article IDs in each cluster, not an accuracy estimate.",
             "Labels and stable topic IDs require review before activation.", ""]
    for topic, group in rows.groupby("topic_id", sort=True):
        name = "Unassigned" if topic == -1 else f"Topic {topic}"
        lines.extend([f"## {name} ({len(group)} articles)", "", keywords.get(topic, ""), ""])
        for row in group.sort_values("id").head(3).itertuples():
            excerpt = " ".join(row.clean_content.split())[:1000]
            lines.extend([f"Article {row.id}:", "", "> " + excerpt, ""])
        lines.extend(["Review decision: pending. Suggested label: pending.", ""])
    label_drafts = [{"topic_id": int(topic), "count": len(group),
                     "keywords": keywords.get(topic, ""), "label": None,
                     "review_status": "pending", "stable_topic_id": None,
                     "sample_article_ids": group.sort_values("id").head(3)['id'].tolist()}
                    for topic, group in rows.groupby("topic_id", sort=True) if topic != -1]
    (out / "label-review.json").write_text(json.dumps({
        "status": "inactive_pending_review", "version": out.name,
        "instructions": "Supply readable labels after reviewing representative articles; map stable IDs only after checking existing catalog meanings. Do not equate cluster IDs with T001-T005.",
        "topics": label_drafts}, indent=2) + "\n", encoding="utf-8")
    (out / "review.md").write_text("\n".join(lines), encoding="utf-8")


SNAPSHOT_COLUMNS = ("id", "content_hash", "clean_content", "is_relevant", "llm_relevant", "processing_status")


def documents_digest(records):
    data = [[r["id"], r["clean_content"]] for r in records]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def make_snapshot(articles):
    records = json.loads(articles.loc[:, list(SNAPSHOT_COLUMNS)].to_json(orient="records", force_ascii=False))
    return {"schema_version": 1, "records": records, "documents_sha256": documents_digest(records)}


def read_snapshot(path):
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != 1 or not isinstance(snapshot.get("records"), list):
        raise ValueError("Unsupported article snapshot format")
    records = snapshot["records"]
    if not records or any(not isinstance(r, dict) or not set(SNAPSHOT_COLUMNS) <= r.keys() for r in records):
        raise ValueError("Snapshot must contain complete article records")
    if snapshot.get("documents_sha256") != documents_digest(records):
        raise ValueError("Snapshot article IDs or text changed: checksum does not match")
    if any(not isinstance(r["id"], int) or isinstance(r["id"], bool) or
           not isinstance(r["clean_content"], str) for r in records):
        raise ValueError("Snapshot IDs must be integers and article text must be strings")
    if len({r["id"] for r in records}) != len(records):
        raise ValueError("Snapshot contains duplicate article IDs")
    articles = pd.DataFrame(records)
    if len(eligible_articles(articles)) != len(articles):
        raise ValueError("Snapshot contains ineligible or duplicate articles")
    return articles


def environment():
    versions = {"python": platform.python_version()}
    for name in LIBRARIES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_manifest(out, manifest):
    (out / "training.json").write_text(json.dumps(manifest, indent=2))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Train a candidate topic model that picks its own number of topics.")
    parser.add_argument("--version", required=True, help="folder name for the candidate, e.g. auto-v1")
    parser.add_argument("--min-topic-size", type=int, default=10,
                        help="smallest cluster that counts as a topic (default 10)")
    parser.add_argument("--snapshot", type=Path, help="Replay the articles.json saved by an earlier run; does not query the database")
    parser.add_argument("--topic-count", type=int, help="Use KMeans to request a fixed topic count; omitted means automatic density clustering. Fixed-count mode assigns every article and ignores minimum topic size.")
    args = parser.parse_args(argv)

    manifest = train(args.version, args.min_topic_size, args.snapshot, args.topic_count)
    print(f"Saved candidate {args.version} to {MODELS_DIR / args.version}: {manifest['topics']} topic(s) "
          f"from {manifest['articles']} article(s), {manifest['unassigned']} unassigned.")
    print("Not registered: normal runs still use the registered model. "
          "Review discovered topics before activating a candidate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
