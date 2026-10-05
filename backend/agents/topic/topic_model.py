#Libraries
import os
import hashlib
import json
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pathlib import Path

import pandas as pd
from bertopic import BERTopic

TOPIC_RESULT_COLUMNS = [
    "article_id", "topic_id", "topic", "topic_keywords", "stable_topic_id", "model_version"
]
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "provisional_topic_model_v2.pkl"
TOPIC_CATALOG_PATH = Path(__file__).resolve().parent / "topic_catalog.json"

def get_model_registration(model_path):
    if not model_path.is_file():
        raise ValueError("Saved topic model is missing. Restore it before running analysis.")
    catalog = json.loads(TOPIC_CATALOG_PATH.read_text())
    registration = catalog["models"].get(model_path.name)
    if registration is None:
        raise ValueError("Saved model is not registered in topic_catalog.json.")
    with model_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != registration["sha256"]:
        raise ValueError("Saved model has changed. Register a reviewed new version before using it.")
    mapping = registration["topic_mapping"]
    if len(set(mapping.values())) != len(mapping) or not set(mapping.values()) <= set(catalog["topics"]):
        raise ValueError("Invalid stable topic mapping in topic_catalog.json.")
    return registration

def get_database():
    # The shared client resolves backend/.env and the SUPABASE_KEY /
    # SUPABASE_ANON_KEY naming in one place. A path built from this
    # file's location breaks whenever the module moves, as it did when
    # it moved under backend/agents/.
    from ..supabase_client import get_client

    return get_client()

def save_topic_results(results):
    if results.empty:
        return 0
    records = results.astype(object).where(results.notna(), None).to_dict(orient="records")
    json.dumps(records, allow_nan=False)
    database = get_database()
    response = database.table("topic_results").upsert(
        records, on_conflict="article_id", ignore_duplicates=True, returning="representation"
    ).execute()
    return len(response.data)

def load_articles(article_ids=None, page_size=500):
    if not isinstance(page_size, int) or isinstance(page_size, bool) or page_size < 1:
        raise ValueError("page_size must be a positive integer")

    if article_ids is not None and not article_ids:
        return pd.DataFrame()

    database = get_database()
    records = []
    offset = 0

    while True:
        query = (
            database.table("articles")
            .select("id, content_hash, clean_content, is_relevant, llm_relevant, processing_status")
            .eq("is_relevant", True)
            .eq("llm_relevant", True)
            .eq("processing_status", "success")
            .order("id")
        )
        if article_ids is not None:
            query = query.in_("id", article_ids)

        response = query.range(offset, offset + page_size - 1).execute()
        page = response.data
        if not page:
            break
        records.extend(page)
        # Advance by the actual count if the server caps pages below page_size.
        offset += len(page)

    return pd.DataFrame(records)

def analyze_topics(articles, topic_count=None, model_path=None):
    """Assign articles with a saved model. topic_count is retained for caller compatibility.

    Topic count is chosen during deliberate training, never during inference.
    """
    if articles.empty:
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)
    articles = articles[
        (articles["is_relevant"] == True)
        & (articles["llm_relevant"] == True)
        & (articles["processing_status"] == "success")
        & articles["clean_content"].fillna("").str.strip().ne("")
    ].copy()
    # Only hashes that are present establish duplicate identity.
    hashes = articles["content_hash"]
    duplicate = hashes.notna() & hashes.ne("") & hashes.duplicated()
    articles = articles[~duplicate].reset_index(drop=True)
    if articles.empty:
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    model_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    registration = get_model_registration(model_path)
    topic_model = BERTopic.load(str(model_path))
    topic_info = topic_model.get_topic_info().set_index("Topic")
    known_topics = {str(topic) for topic in topic_info.index if topic != -1}
    if known_topics != set(registration["topic_mapping"]):
        raise ValueError("Saved model topics do not match the registered topic mapping.")
    topics, _ = topic_model.transform(articles["clean_content"].tolist())
    labels = registration["labels"]
    results = pd.DataFrame({
        "article_id": articles["id"].tolist(),
        "topic_id": topics,
        "topic": ["Unassigned" if topic == -1 else labels[str(topic)] for topic in topics],
        "topic_keywords": [
            "" if topic == -1 else "; ".join(word for word, _ in (topic_model.get_topic(topic) or []))
            for topic in topics
        ],
        "stable_topic_id": [
            None if topic == -1 else registration["topic_mapping"][str(topic)] for topic in topics
        ],
        "model_version": registration["version"],
    }, columns=TOPIC_RESULT_COLUMNS)
    print(f"Reused saved topic model: {model_path.name} ({registration['version']})")
    return results

def run_topic_agent(articles, topic_count=None):
    try:
        results = analyze_topics(articles, topic_count)

        return {
            "agent": "topic",
            "status": "success" if not results.empty else "skipped",
            "results": results,
            "error": None,
        }

    except Exception as exc:
        return {
            "agent": "topic",
            "status": "failed",
            "results": pd.DataFrame(columns=TOPIC_RESULT_COLUMNS),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }

class TopicAgent:
    name = "topic"

    def __init__(self, topic_count=6):
        self.topic_count = topic_count

    def run(self, ctx):
        articles = load_articles(ctx.approved_ids)

        if articles.empty:
            return {
                "processed": 0,
                "article_ids": [],
            }

        results = analyze_topics(articles, topic_count=self.topic_count)
        inserted = save_topic_results(results)

        return {
            "processed": len(results),
            "inserted": inserted,
            "preserved": len(results) - inserted,
            "article_ids": results["article_id"].tolist(),
        }

if __name__ == "__main__":
    try:
        articles = load_articles()
        print(f"Loaded {len(articles)} articles from Supabase.")
    except Exception as exc:
        print(
            f"Database load failed: "
            f"{type(exc).__name__}: {exc}"
        )
        raise SystemExit(2)

    outcome = run_topic_agent(articles, topic_count=6)

    if outcome["status"] == "failed":
        error = outcome["error"]
        print(
            f"Topic analysis failed: "
            f"{error['type']}: {error['message']}"
        )
        raise SystemExit(1)

    if outcome["status"] == "skipped":
        print("Topic analysis skipped: no eligible articles.")
        raise SystemExit(0)

    try:
        inserted = save_topic_results(outcome["results"])
        print(
            f"Analyzed {len(outcome['results'])} articles. Inserted {inserted} new results; "
            f"preserved {len(outcome['results']) - inserted} existing assignments."
        )
    except Exception as exc:
        print(
            f"Database save failed: "
            f"{type(exc).__name__}: {exc}"
        )
        raise SystemExit(3)
