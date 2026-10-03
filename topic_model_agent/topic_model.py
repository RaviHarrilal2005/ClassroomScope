#Libraries
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

import pandas as pd
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from umap import UMAP

TOPIC_RESULT_COLUMNS = ["article_id", "topic_id", "topic", "topic_keywords"]

REVIEWED_LABELS = {
    # Labels observed in the latest full-data run.
    "0_learning_according_policy_department":
        "AI adoption and policies in schools",
    "1_university_work_cheating_like":
        "Academic integrity and assessment",
    "2_social_media_learning_health":
        "General education and school operations",
    "3_university_college_financial_programs":
        "Education access, finances, and governance",
    "4_learning_thinking_reply_percent":
        "Critical thinking and AI dependence",
}

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

    database = get_database()
    records = results.to_dict(orient="records")
    database.table("topic_results").upsert(records, on_conflict="article_id").execute()

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

def analyze_topics(articles, topic_count=None):

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    # Require both relevance checks, successful processing, and usable text.
    articles = articles[
        (articles["is_relevant"] == True)
        & (articles["llm_relevant"] == True)
        & (articles["processing_status"] == "success")
        & articles["clean_content"].fillna("").str.strip().ne("")
    ].copy()
    # Filter before deduplication so an ineligible copy cannot hide an eligible one.
    articles = articles.drop_duplicates(subset="content_hash").reset_index(drop=True)

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=TOPIC_RESULT_COLUMNS)

    article_content = articles["clean_content"].tolist()

    # Small batches cannot reliably support topic discovery.
    if len(articles) < 10:
        return pd.DataFrame({
            "article_id": articles["id"].tolist(),
            "topic_id": [-1] * len(articles),
            "topic": ["Unassigned"] * len(articles),
            "topic_keywords": [""] * len(articles),
        })

    def build_topic_model(min_topic_size: int = 10):
        #Model to filter out stop words
        domain_stop_words = {
        "ai", "artificial", "intelligence", "education", "educational",
        "student", "students", "school", "schools", "teacher", "teachers",
        "said", "says", "say", "new", "use", "used", "using",
        "educators", "tools", "tool", "help", "systems", "generated",
        "technology", "information", "districts", "district", "automated", "support", "12"
        }

        vectorizer_model = CountVectorizer(stop_words=list(ENGLISH_STOP_WORDS | domain_stop_words), ngram_range=(1, 1), min_df=1, max_df=1.0)

        umap_model = UMAP(n_neighbors=8, n_components=5, min_dist=0.0, metric="cosine", random_state=42)

        embedding_model = SentenceTransformer("all-mpnet-base-v2")

        topic_model = BERTopic(embedding_model=embedding_model, vectorizer_model=vectorizer_model, umap_model=umap_model, min_topic_size=min_topic_size, nr_topics=topic_count)

        return topic_model, embedding_model

    def build_topic_results(articles):

        return articles[["id", "topic_id", "topic_label", "topic_keywords"]].rename(
        columns={
            "id": "article_id",
            "topic_label": "topic",
        }
    ).copy()

    topic_model, embedding_model = build_topic_model()

    embeddings = embedding_model.encode(article_content)

    #Find topics
    topics, probabilities = topic_model.fit_transform(article_content, embeddings)

    topic_info = topic_model.get_topic_info().set_index("Topic")

    if -1 in topic_info.index:
        topic_info.loc[-1, "Name"] = "Unassigned"

    articles["topic_id"] = topics
    articles["topic_label"] = articles["topic_id"].map(topic_info["Name"])
    articles["topic_label"] = articles["topic_label"].replace(REVIEWED_LABELS)

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

    return topic_results

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
        save_topic_results(results)

        return {
            "processed": len(results),
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
