#Libraries
import os
import hashlib
import json
import threading
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from postgrest.exceptions import APIError

import pandas as pd
from bertopic import BERTopic

TOPIC_RESULT_COLUMNS = [
    "article_id", "topic_id", "topic", "topic_keywords", "stable_topic_id", "model_version"
]
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent / "models" / "provisional_topic_model_v2.pkl"
TOPIC_CATALOG_PATH = Path(__file__).resolve().parent / "topic_catalog.json"
EMERGING_POOL_PATH = DEFAULT_MODEL_PATH.parent / "emerging_topic_pool.json"
_POOL_LOCK = threading.Lock()


def save_emerging_candidates(articles, results, pool_path=None):
    """Queue unassigned text for review; never create topics or revise assignments."""
    candidates = results[results["topic_id"] == -1]
    if candidates.empty:
        return 0
    path = Path(pool_path) if pool_path is not None else EMERGING_POOL_PATH
    texts = articles.set_index("id")["clean_content"].to_dict()
    timestamp = datetime.now(timezone.utc).isoformat()
    with _POOL_LOCK:
        pool = json.loads(path.read_text()) if path.is_file() else {"schema_version": 1, "candidates": []}
        if pool.get("schema_version") != 1:
            raise ValueError("Unsupported emerging-topic pool version")
        keys = {
            (str(row["article_id"]), row["model_version"], row["text_sha256"])
            for row in pool["candidates"]
        }
        added = 0
        for row in candidates.to_dict(orient="records"):
            text = texts[row["article_id"]]
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            key = (str(row["article_id"]), row["model_version"], digest)
            if key in keys:
                continue
            pool["candidates"].append({
                "article_id": row["article_id"],
                "model_version": row["model_version"],
                "text_sha256": digest,
                "excerpt": " ".join(text.split())[:1000],
                "review_status": "pending",
                "review_notes": "",
                "first_seen_at": timestamp,
            })
            keys.add(key)
            added += 1
        if added:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                    temporary_path = Path(stream.name)
                    json.dump(pool, stream, indent=2)
                    stream.write("\n")
                temporary_path.replace(path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
        return added


def get_model_registration(model_path):
    """Bind reviewed topic IDs to an exact saved model, not a reusable filename."""
    catalog = json.loads(TOPIC_CATALOG_PATH.read_text())
    registration = catalog["models"].get(model_path.name)
    if registration is None:
        raise ValueError("Model is not registered in topic_catalog.json; review and register it first")
    if not model_path.is_file():
        raise ValueError("Registered model file is missing; restore it rather than retraining under the same version")
    with model_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != registration["sha256"]:
        raise ValueError("Model file changed; register the reviewed model under a new version")
    mapping = registration["topic_mapping"]
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Model registration maps multiple clusters to the same permanent topic")
    if any(topic not in catalog["topics"] for topic in mapping.values()):
        raise ValueError("Model registration references an unknown permanent topic")
    return registration

def get_database():
    env_path = Path(__file__).resolve().parents[1] / "backend" / ".env"
    load_dotenv(env_path)

    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_KEY"],
    )

def save_topic_results(results):
    if results.empty:
        return

    # Pandas uses NaN for missing values; the database expects JSON null.
    # Convert to object first so numeric columns can retain Python None.
    records = results.astype(object).where(results.notna(), None).to_dict(orient="records")
    json.dumps(records, allow_nan=False)
    database = get_database()
    # Preserve existing article assignments; topic revisions require a separate workflow.
    try:
        database.table("topic_results").upsert(
            records, on_conflict="article_id", ignore_duplicates=True
        ).execute()
    except APIError as exc:
        if exc.code in {"PGRST204", "42703"}:
            raise RuntimeError(
                "Apply the topic identity migration before saving: "
                "supabase/migrations/20261003000100_topic_identity.sql"
            ) from exc
        raise

def load_articles(article_ids=None, page_size=500):
    """Load eligible articles in ID order until the database returns no more rows."""
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


def analyze_topics(articles, topic_count=None, summary=None, model_path=None):
    model_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    if summary is None:
        summary = {}
    summary.update({
        "loaded": len(articles),
        "eligible": 0,
        "excluded_ineligible": 0,
        "excluded_blank_text": 0,
        "excluded_source_review": 0,
        "duplicates_removed": 0,
        "analyzed": 0,
        "assigned": 0,
        "unassigned": 0,
    })

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    # Require both relevance checks, successful processing, and usable text.
    eligible = (
        (articles["is_relevant"] == True)
        & (articles["llm_relevant"] == True)
        & (articles["processing_status"] == "success")
    ).fillna(False)
    summary["eligible"] = int(eligible.sum())
    summary["excluded_ineligible"] = len(articles) - summary["eligible"]
    articles = articles[eligible].copy()
    has_text = articles["clean_content"].fillna("").str.strip().ne("")
    summary["excluded_blank_text"] = int((~has_text).sum())
    articles = articles[has_text].copy()
    # Filter before deduplication so an ineligible copy cannot hide an eligible one.
    before_deduplication = len(articles)
    articles = articles.drop_duplicates(subset="content_hash").reset_index(drop=True)
    summary["duplicates_removed"] = before_deduplication - len(articles)

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    article_content = articles["clean_content"].tolist()
    registration = get_model_registration(model_path)

    def build_topic_results(articles):

        return articles[["id", "topic_id", "topic_label", "topic_keywords"]].rename(
        columns={
            "id": "article_id",
            "topic_label": "topic",
        }
    ).copy()

    # Inference requires a registered saved model; training is a deliberate operation.
    topic_model = BERTopic.load(str(model_path))
    topics, probabilities = topic_model.transform(article_content)
    print(f"Reused saved topic model: {model_path.name}")

    topic_info = topic_model.get_topic_info().set_index("Topic")
    known_topics = {str(topic) for topic in topic_info.index if topic != -1}
    if known_topics != set(registration["topic_mapping"]):
        raise ValueError("Model topics do not match the reviewed topic registration")

    # Reviewed labels belong to this saved model, not generated names from old runs.
    label_column = "CustomName" if "CustomName" in topic_info.columns else "Name"
    if -1 in topic_info.index:
        topic_info.loc[-1, label_column] = "Unassigned"

    articles["topic_id"] = topics
    articles["topic_label"] = articles["topic_id"].map(topic_info[label_column])

    topic_keywords = {
    topic_id: "; ".join(
        word for word, _ in (topic_model.get_topic(topic_id) or [])
    )
    for topic_id in set(topics)
    if topic_id != -1
}

    articles["topic_keywords"] = (
        articles["topic_id"]
        .map(topic_keywords)
        .fillna("")
    )

    topic_results = build_topic_results(articles)
    topic_results["stable_topic_id"] = [
        None if topic == -1 else registration["topic_mapping"][str(topic)]
        for topic in topics
    ]
    topic_results["model_version"] = registration["version"]
    summary["analyzed"] = len(topic_results)
    summary["unassigned"] = int((topic_results["topic_id"] == -1).sum())
    summary["assigned"] = summary["analyzed"] - summary["unassigned"]

    return topic_results

def run_topic_agent(articles, topic_count=None):
    summary = {}
    try:
        results = analyze_topics(articles, topic_count, summary=summary)
        summary["emerging_candidates_added"] = save_emerging_candidates(articles, results)

        return {
            "agent": "topic",
            "status": "success" if not results.empty else "skipped",
            "results": results,
            "summary": summary,
            "error": None,
        }

    except Exception as exc:
        return {
            "agent": "topic",
            "status": "failed",
            "results": pd.DataFrame(columns=TOPIC_RESULT_COLUMNS),
            "summary": summary,
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

        summary = {}
        results = analyze_topics(articles, topic_count=self.topic_count, summary=summary)
        summary["emerging_candidates_added"] = save_emerging_candidates(articles, results)
        save_topic_results(results)

        return {
            "processed": len(results),
            "article_ids": results["article_id"].tolist(),
            "summary": summary,
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
    print("Topic processing summary:")
    for name, count in outcome["summary"].items():
        print(f"  {name.replace('_', ' ')}: {count}")

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
        save_topic_results(outcome["results"])
        print(
            f"Saved {len(outcome['results'])} "
            "topic results to Supabase."
        )
    except Exception as exc:
        print(
            f"Database save failed: "
            f"{type(exc).__name__}: {exc}"
        )
        raise SystemExit(3)
