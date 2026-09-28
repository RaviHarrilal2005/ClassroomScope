#Libraries
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import pandas as pd
from sentence_transformers import SentenceTransformer
from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from umap import UMAP

def analyze_topics():

    #Loads CSV file of articles
    articles = pd.read_csv("articles_rows.csv").drop_duplicates(subset="content_hash").reset_index(drop=True)
    articles = articles[(articles["is_relevant"] == True) & (articles["processing_status"] == "success") & articles["clean_content"].fillna("").str.strip().ne("")].copy()
    articles = articles.reset_index(drop = True)

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
        # Keep the original article ID so the aggregator can match other agents' results.
        return articles[["id", "topic_id", "topic_label"]].rename(
            columns={"id": "article_id"}
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
    results = analyze_topics()