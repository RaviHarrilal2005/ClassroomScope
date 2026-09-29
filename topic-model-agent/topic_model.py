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

def load_articles():
    database = get_database()
    response = (
        database.table("articles")
        .select("id, content_hash, clean_content, is_relevant, processing_status")
        .eq("is_relevant", True)
        .eq("processing_status", "success")
        .order("id")
        .execute()
    )
    return pd.DataFrame(response.data)


def analyze_topics(articles):

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=["article_id", "topic"])

    # Your existing deduplication and filtering continue here.
    #Loads CSV file of articles
    articles = articles.drop_duplicates(subset="content_hash").reset_index(drop=True)
    articles = articles[(articles["is_relevant"] == True) & (articles["processing_status"] == "success") & articles["clean_content"].fillna("").str.strip().ne("")].copy()
    articles = articles.reset_index(drop = True)

    if articles.empty:
        print("No eligible articles to analyze.")
        return pd.DataFrame(columns=["article_id", "topic"])

    article_content = articles["clean_content"].tolist()

    def build_topic_model(min_topic_size: int = 10):
        #Model to filter out stop words
        domain_stop_words = {
        "ai", "artificial", "intelligence", "education", "educational",
        "student", "students", "school", "schools", "teacher", "teachers",
        "said", "says", "say", "new", "use", "used", "using",
        "educators", "tools", "tool", "help", "systems", "generated",
        "technology", "information", "districts", "district", "automated", "support", "12"
        }

        vectorizer_model = CountVectorizer(stop_words=list(ENGLISH_STOP_WORDS | domain_stop_words), ngram_range=(1, 1), min_df=1, max_df=0.9)

        umap_model = UMAP(n_neighbors=8, n_components=5, min_dist=0.0, metric="cosine", random_state=42)

        embedding_model = SentenceTransformer("all-mpnet-base-v2")

        topic_model = BERTopic(embedding_model=embedding_model, vectorizer_model=vectorizer_model, umap_model=umap_model, min_topic_size=min_topic_size, nr_topics=None)

        return topic_model, embedding_model

    def build_topic_results(articles):
        return articles[["id", "topic_label"]].rename(
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

    topic_results = build_topic_results(articles)

    return topic_results

if __name__ == "__main__":
    articles = load_articles()
    print(f"Loaded {len(articles)} articles from Supabase.")

    results = analyze_topics(articles)
    save_topic_results(results)
    print(f"Saved {len(results)} topic results to Supabase.")