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
    "article_id", "topic_id", "topic", "topic_keywords", "stable_topic_id", "model_version",
    "suggested_topic", "suggested_stable_topic_id", "suggested_topic_similarity",
    "suggested_topic_gap", "suggestion_method", "original_topic_id", "assignment_method", "mapping_version", "unassigned_reason"
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
    # Bind provenance to the actual catalog, not a proposed future definition.
    payload = {"topics": catalog["topics"], "topic_mapping": mapping,
               "labels": registration["labels"]}
    registration["mapping_version"] = "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
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

def use_installed_umap_functions(topic_model, distances=None):
    """Swap the pickle's copies of umap's distance functions for the installed ones.

    The saved model carries umap's numba distance functions compiled for the
    Python that trained it (3.12). On any other Python version numba cannot
    compile that bytecode and transform fails with "IndexError: pop from empty
    list". The installed functions are the same code built for this Python, so
    the model's topics do not change.
    """
    if distances is None:
        import umap.distances as distances
    umap_model = topic_model.umap_model
    for attr in ("_input_distance_func", "_inverse_distance_func", "_output_distance_func"):
        func = getattr(umap_model, attr, None)
        if func is not None:
            setattr(umap_model, attr, getattr(distances, func.py_func.__name__))

def eligible_articles(articles):
    """Apply shared relevance, text, and duplicate rules for training and inference."""
    if articles.empty:
        return articles.copy()
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
    return articles

def add_unassigned_suggestions(results, documents, topic_model, registration):
    """Suggest strong topic fits for review without changing final assignments."""
    import numpy as np
    positions = [i for i, topic in enumerate(results["topic_id"]) if topic == -1]
    if not positions:
        return results
    # BERTopic stores topic vectors in sorted topic-ID order, including -1.
    ordered = sorted(topic_model.get_topics())
    candidates = [(i, topic) for i, topic in enumerate(ordered) if topic != -1]
    if len(candidates) < 2:
        return results
    vectors = np.asarray(topic_model.topic_embeddings_, dtype=float)
    if vectors.ndim != 2 or len(vectors) != len(ordered):
        raise ValueError("Saved topic vectors do not match topic IDs")
    vectors = vectors[[i for i, _ in candidates]]
    # Encode singly as well: batch padding/numerics must not influence a threshold decision.
    embeddings = np.asarray([topic_model.embedding_model.embed_documents(
        [documents[i]], verbose=False
    )[0] for i in positions], dtype=float)
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(vectors).all() or (norms == 0).any():
        raise ValueError("Saved topic vectors are invalid")
    for position, embedding in zip(positions, embeddings):
        results.at[position, "suggestion_method"] = "topic-cosine-0.85-gap-0.03-review-only-v3"
        norm = np.linalg.norm(embedding)
        if not np.isfinite(embedding).all() or norm == 0:
            continue
        scores = (vectors @ embedding) / (norms * norm)
        ranking = np.argsort(-scores, kind="stable")
        best = float(scores[ranking[0]])
        gap = best - float(scores[ranking[1]])
        results.at[position, "suggested_topic_similarity"] = best
        results.at[position, "suggested_topic_gap"] = gap
        if best >= 0.85 and gap >= 0.03:
            topic = str(candidates[ranking[0]][1])
            results.at[position, "suggested_topic"] = registration["labels"][topic]
            results.at[position, "suggested_stable_topic_id"] = registration["topic_mapping"][topic]
    return results

def analyze_topics(articles, topic_count=None, model_path=None):
    """Assign articles to the topics in a saved model.

    Topic count is chosen during deliberate training, never during inference.
    """
    if articles.empty:
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)
    articles = eligible_articles(articles)
    if articles.empty:
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    model_path = Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH
    registration = get_model_registration(model_path)
    topic_model = BERTopic.load(str(model_path))
    use_installed_umap_functions(topic_model)
    topic_info = topic_model.get_topic_info().set_index("Topic")
    known_topics = {str(topic) for topic in topic_info.index if topic != -1}
    if known_topics != set(registration["topic_mapping"]):
        raise ValueError("Saved model topics do not match the registered topic mapping.")
    documents = articles["clean_content"].tolist()
    strategy = registration.get("embedding_strategy", "truncate-v1")
    saved_strategy = getattr(topic_model, "article_embedding_strategy", "truncate-v1")
    if saved_strategy != strategy:
        raise ValueError("Saved model embedding strategy does not match its registration")
    if strategy != "truncate-v1":
        raise ValueError(f"Unsupported article embedding strategy: {strategy}")
    # UMAP transform positions depend on batch composition. A canonical singleton
    # transform gives each article the same inference context, regardless of callers.
    topics = []
    for document in documents:
        prediction, _ = topic_model.transform([document])
        if len(prediction) != 1:
            raise ValueError("Single-article inference returned an invalid prediction count")
        topics.append(int(prediction[0]))
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
        "mapping_version": registration.get("mapping_version"),
        "unassigned_reason": ["uncertain_fit" if topic == -1 else None for topic in topics],
        "original_topic_id": topics,
        "assignment_method": "bertopic-single-document-v1",
    }, columns=TOPIC_RESULT_COLUMNS)
    results = add_unassigned_suggestions(results, documents, topic_model, registration)
    print(f"Reused saved topic model: {model_path.name} ({registration['version']})")
    return results

def summarize_topic_results(results):
    """Count final assignments; review-only suggestions remain Unassigned."""
    unassigned = int(results["topic_id"].eq(-1).sum())
    return {
        "processed": len(results),
        "assigned": len(results) - unassigned,
        "unassigned": unassigned,
    }

def run_topic_agent(articles):
    try:
        results = analyze_topics(articles)

        return {
            "agent": "topic",
            "status": "success" if not results.empty else "skipped",
            "results": results,
            **summarize_topic_results(results),
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

    def run(self, ctx):
        articles = load_articles(ctx.approved_ids)

        if articles.empty:
            return {
                "processed": 0,
                "assigned": 0,
                "unassigned": 0,
                "article_ids": [],
            }

        results = analyze_topics(articles)
        inserted = save_topic_results(results)

        return {
            **summarize_topic_results(results),
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

    outcome = run_topic_agent(articles)

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
            f"Processed {outcome['processed']} articles: "
            f"{outcome['assigned']} assigned, {outcome['unassigned']} unassigned. "
            f"Inserted {inserted} new results; "
            f"preserved {len(outcome['results']) - inserted} existing assignments."
        )
    except Exception as exc:
        print(
            f"Database save failed: "
            f"{type(exc).__name__}: {exc}"
        )
        raise SystemExit(3)
