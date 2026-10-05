"""
Train a candidate topic model that chooses its own number of topics.

    python -m agents.topic.train_auto --version auto-v1        (from backend/)

The same pipeline that trained provisional-v2 (the training code in commit
fff48c2), except nr_topics=None: the clustering decides how many topics
there are. min_topic_size is a cluster-size setting, not a topic count.
See TOPIC_IDENTITY.md, "Separate automatic discovery training".

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
LIBRARIES = ("bertopic", "umap-learn", "hdbscan", "sentence-transformers", "numba")


def build_model(min_topic_size):
    from bertopic import BERTopic
    from sentence_transformers import SentenceTransformer
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer
    from umap import UMAP

    return BERTopic(
        embedding_model=SentenceTransformer(EMBEDDING_MODEL),
        vectorizer_model=CountVectorizer(
            stop_words=list(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS), ngram_range=(1, 1), min_df=1, max_df=1.0
        ),
        umap_model=UMAP(**UMAP_SETTINGS),
        min_topic_size=min_topic_size,
        nr_topics=None,
    )


def train(version, min_topic_size=10):
    """Train, then save the candidate to MODELS_DIR/<version>. Returns its manifest."""
    if not VERSION_NAME.fullmatch(version):
        raise ValueError(f"--version must be a plain folder name like auto-v1, not {version!r}")
    if min_topic_size < 2:
        raise ValueError("--min-topic-size must be at least 2")

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
            "min_topic_size": min_topic_size,
            "umap": UMAP_SETTINGS,
            "stop_words": "scikit-learn's English list plus DOMAIN_STOP_WORDS in train_auto.py",
        },
        "environment": environment(),
    }
    write_manifest(out, manifest)
    try:
        articles = eligible_articles(load_articles())
        if len(articles) < MIN_ARTICLES:
            raise ValueError(f"Found {len(articles)} eligible article(s); training needs at least {MIN_ARTICLES}.")

        model = build_model(min_topic_size)
        topics, _ = model.fit_transform(articles["clean_content"].tolist())
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
    args = parser.parse_args(argv)

    manifest = train(args.version, args.min_topic_size)
    print(f"Saved candidate {args.version} to {MODELS_DIR / args.version}: {manifest['topics']} topic(s) "
          f"from {manifest['articles']} article(s), {manifest['unassigned']} unassigned.")
    print("Not registered: normal runs still use the registered model. "
          "Review it before mapping any topic to T001-T005.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
