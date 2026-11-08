"""
Sentiment agent.

Labels each relevant article as positive, neutral or negative, with a
confidence score.

  main method:  RoBERTa model trained on (financial) news   -> method "roberta_news"
  baseline:     VADER, a word-list method                    -> method "vader"

Reads articles from the Supabase `articles` table and writes rows to
`sentiment_results` (article_id, sentiment, confidence, method).

In the pipeline:
    from agents.sentiment.sentiment_agent import SentimentAgent
    SentimentAgent().run(ctx)            # labels ctx.approved_ids
    SentimentAgent("vader").run(ctx)     # baseline / fallback

By itself (from the backend folder, or with the run button):
    python -m agents.sentiment.sentiment_agent            # shows what it would do, saves nothing
    python -m agents.sentiment.sentiment_agent --test 3   # labels 3 articles and prints them, saves nothing
    python -m agents.sentiment.sentiment_agent --save     # labels articles with no result yet and saves them
    add --vader to any of these to use the VADER baseline instead
    add --v2 to any of these to score with the new version and save as "roberta_news_v2"

Nothing is loaded or read when this file is imported. The models load
the first time they are needed.
"""
import re
import sys
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from orchestrator.agents import Agent
else:
    try:
        from orchestrator.agents import Agent
    except ImportError:
        # running this file by itself, outside the team's repo: a plain stand-in
        class Agent:
            pass

MODEL_NAME = "Jean-Baptiste/roberta-large-financial-news-sentiment-en"
# "roberta_news_v2" is the same model, run with the headline and sentence-aligned
# chunks. It is saved under its own name so the older "roberta_news" rows stay untouched.
METHODS = ("roberta_news", "roberta_news_v2", "vader")

# RoBERTa reads at most 512 tokens, so articles are split into chunks of at
# most 480 (a little under the limit, because the model adds 2 special tokens)
CHUNK_SIZE = 480

# the original "roberta_news" method cuts fixed 500-token windows
ORIGINAL_CHUNK_SIZE = 500

# how many rows to read or write in one request
BATCH = 200

# decimal places for the confidence score that gets saved
DECIMALS = 3

# results below this confidence are less reliable (counted in the summary)
LOW_CONFIDENCE = 0.6

# the models are loaded once, the first time they are needed
_sentiment_model = None
_tokenizer = None
_vader = None


# ---------------- models ----------------

def load_roberta():
    global _sentiment_model, _tokenizer
    if _sentiment_model is None or _tokenizer is None:
        from transformers import pipeline, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _sentiment_model = pipeline("text-classification", model=MODEL_NAME, tokenizer=tokenizer)
        _tokenizer = tokenizer
    return _sentiment_model, _tokenizer


def load_vader():
    global _vader
    if _vader is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _vader = SentimentIntensityAnalyzer()
    return _vader


def split_into_chunks(text, count_tokens, chunk_size=CHUNK_SIZE):
    """
    Cut an article into chunks that end at sentence boundaries, each at
    most chunk_size tokens, so the whole article is read and no sentence
    is cut in half. A single sentence longer than chunk_size is cut by words.

    count_tokens is a function that returns the token count of a string.
    Returns a list of (chunk_text, token_count).
    """
    # sentences end at . ! ? followed by a space, or at a new line
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    pieces = [p.strip() for p in pieces if p and p.strip() != ""]

    chunks = []
    current = []
    current_length = 0

    def close_chunk():
        nonlocal current, current_length
        if current:
            chunks.append((" ".join(current), current_length))
        current = []
        current_length = 0

    for piece in pieces:
        length = count_tokens(piece)

        if length > chunk_size:
            # one huge "sentence" (a table, a list with no full stops): cut it by words
            close_chunk()
            words = piece.split()
            part = []
            for word in words:
                trial = " ".join(part + [word])
                if part and count_tokens(trial) > chunk_size:
                    chunks.append((" ".join(part), count_tokens(" ".join(part))))
                    part = [word]
                else:
                    part.append(word)
            if part:
                chunks.append((" ".join(part), count_tokens(" ".join(part))))
            continue

        if current_length + length > chunk_size:
            close_chunk()
        current.append(piece)
        current_length += length

    close_chunk()
    return chunks


def analyze_sentiment(text, title=None, method="roberta_news_v2"):
    """
    RoBERTa sentiment for one article. Returns (label, confidence, scores).

    roberta_news_v2: the headline is put in front of the article text,
    because in news the headline carries a lot of the tone, and the article
    is cut into sentence-aligned chunks.
    roberta_news: the original way, kept so its rows stay comparable: no
    headline, and fixed windows of ORIGINAL_CHUNK_SIZE tokens.

    Either way the whole article is read, every chunk is scored, and the
    chunk scores are averaged with longer chunks counting more.
    """
    # stop if the article has no text (dividing by 0 chunks would crash)
    if not text or text.strip() == "":
        raise ValueError("Article has no text to analyze")

    sentiment_model, tokenizer = load_roberta()

    if method == "roberta_news_v2":
        if title and title.strip() != "":
            text = title.strip() + ". " + text.strip()

        def count_tokens(piece):
            return len(tokenizer.encode(piece, add_special_tokens=False))

        chunks = split_into_chunks(text, count_tokens)
    else:
        tokens = tokenizer.encode(text, add_special_tokens=False)
        chunks = []
        for i in range(0, len(tokens), ORIGINAL_CHUNK_SIZE):
            chunk_tokens = tokens[i:i + ORIGINAL_CHUNK_SIZE]
            chunks.append((tokenizer.decode(chunk_tokens, skip_special_tokens=True), len(chunk_tokens)))
    if not chunks:
        raise ValueError("Article has no text to analyze")

    scores = {"positive": 0, "neutral": 0, "negative": 0}
    total_tokens = 0

    # score all chunks of the article together (faster than one at a time)
    chunk_texts = [chunk_text for chunk_text, chunk_length in chunks]
    # with top_k=None it returns one list of label scores per chunk; transformers'
    # type hints say a flat list, so tell the type checker not to trust them
    all_results = cast(list, sentiment_model(chunk_texts, top_k=None, truncation=True, batch_size=16))

    for (chunk_text, chunk_length), results in zip(chunks, all_results):
        for result in results:
            label = result["label"].lower()
            if label not in scores:
                raise ValueError("Model gave an unexpected label: " + result["label"])
            # longer chunks count more than short ones
            scores[label] += result["score"] * chunk_length

        total_tokens += chunk_length

    if total_tokens == 0:
        raise ValueError("Article has no text to analyze")

    for label in scores:
        scores[label] = scores[label] / total_tokens

    final_sentiment = max(scores, key=lambda label: scores[label])
    confidence = scores[final_sentiment]

    scores["chunks"] = len(chunks)
    return final_sentiment, confidence, scores


def vader_sentiment(text):
    """VADER sentiment for one article. Returns (label, average compound score)."""
    # our adaptation of VADER for full articles:
    # score each sentence, then average the sentence scores
    if not text or text.strip() == "":
        raise ValueError("Article has no text to analyze")

    vader = load_vader()

    # split after . ! or ? only when a space follows, so "3.5" or "U.S.A" stay whole
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s for s in sentences if s.strip() != ""]

    # stop if there are no sentences (dividing by 0 would crash)
    if len(sentences) == 0:
        raise ValueError("Article has no text to analyze")

    total = 0
    for sentence in sentences:
        total += vader.polarity_scores(sentence)["compound"]

    average = total / len(sentences)

    # standard VADER cutoffs
    if average >= 0.05:
        label = "positive"
    elif average <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return label, average


def label_article(text, method, title=None):
    """Returns (sentiment, confidence) for one article with the chosen method."""
    if method in ("roberta_news", "roberta_news_v2"):
        label, confidence, scores = analyze_sentiment(text, title, method)
        return label, float(confidence)

    # VADER has no confidence score, so the size of its score is used instead
    label, score = vader_sentiment(text)
    return label, min(abs(float(score)), 1.0)


# ---------------- database ----------------

def get_database():
    # in the pipeline, use the client the whole team shares
    try:
        from ..supabase_client import get_client

        return get_client()
    except ImportError:
        pass

    # when this file is run by itself, connect using the .env file
    import os
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY is missing from the .env file")
    return create_client(url, key)


def load_articles(database, article_ids=None):
    """
    Relevant, successfully cleaned articles, without duplicates.

    Relevant means Juan's rule: llm_relevant = true AND processing_status = success.

    article_ids  only these articles (the pipeline passes ctx.approved_ids).
                 None means every relevant article.
    """
    columns = "id, title, clean_content, content_hash"
    rows = []

    if article_ids is not None:
        ids = list(article_ids)
        for start in range(0, len(ids), BATCH):
            response = (
                database.table("articles")
                .select(columns)
                .in_("id", ids[start:start + BATCH])
                .eq("llm_relevant", True)
                .eq("processing_status", "success")
                .execute()
            )
            rows.extend(response.data or [])
    else:
        start = 0
        while True:
            response = (
                database.table("articles")
                .select(columns)
                .eq("llm_relevant", True)
                .eq("processing_status", "success")
                .order("id")
                .range(start, start + BATCH - 1)
                .execute()
            )
            page = response.data or []
            rows.extend(page)
            if len(page) < BATCH:
                break
            start += BATCH

    rows.sort(key=lambda row: row["id"])

    # content_hash is the same for two copies of the same article,
    # so keep the first copy and skip the rest (like the topic agent)
    articles = []
    seen_hashes = set()
    for row in rows:
        if not row.get("clean_content") or row["clean_content"].strip() == "":
            continue
        content_hash = (row.get("content_hash") or "").strip()
        if content_hash and content_hash in seen_hashes:
            continue
        if content_hash:
            seen_hashes.add(content_hash)
        articles.append(row)

    return articles


def find_done(database, article_ids, method):
    """Article ids that already have a sentiment row from this method."""
    done = set()
    ids = list(article_ids)
    for start in range(0, len(ids), BATCH):
        response = (
            database.table("sentiment_results")
            .select("article_id")
            .in_("article_id", ids[start:start + BATCH])
            .eq("method", method)
            .execute()
        )
        for row in response.data or []:
            done.add(row["article_id"])
    return done


def save_results(database, rows):
    """
    Add new rows to sentiment_results. Never changes or deletes existing rows.

    Checks again right before saving, so two runs at the same time
    do not write the same article twice.
    """
    by_method = {}
    for row in rows:
        by_method.setdefault(row["method"], []).append(row)

    new_rows = []
    for method, group in by_method.items():
        done = find_done(database, [row["article_id"] for row in group], method)
        new_rows.extend(row for row in group if row["article_id"] not in done)

    for start in range(0, len(new_rows), BATCH):
        database.table("sentiment_results").insert(new_rows[start:start + BATCH]).execute()
    return len(new_rows)


# ---------------- the agent ----------------

class SentimentAgent(Agent):
    """
    Pipeline agent. run(ctx) labels the approved articles that do not
    have a result from this method yet and writes them to sentiment_results.

    method  "roberta_news" (default) or "vader" (the baseline / fallback)
    """

    name = "sentiment"

    def __init__(self, method="roberta_news"):
        if method not in METHODS:
            raise ValueError("method must be one of " + str(METHODS))
        self.method = method
        self.name = "sentiment_" + method

    def run(self, ctx):
        return run_sentiment(article_ids=ctx.approved_ids, method=self.method, save=True)


def run_sentiment(article_ids=None, method="roberta_news", save=True, limit=None, show=False):
    """
    Label articles and (if save is True) write the results.

    Returns a summary dict. Raises an error if something goes wrong, so
    the pipeline coordinator can see the failure. It does not retry.
    """
    if method not in METHODS:
        raise ValueError("method must be one of " + str(METHODS))

    # the pipeline gave no articles: nothing to do, and no need to load the model
    if article_ids is not None and len(article_ids) == 0:
        return {"processed": 0, "analyzed": 0, "skipped_existing": 0,
                "failed": 0, "failed_ids": [], "low_confidence": 0, "method": method}

    database = get_database()

    articles = load_articles(database, article_ids)
    done = find_done(database, [a["id"] for a in articles], method)
    todo = [a for a in articles if a["id"] not in done]

    if limit is not None:
        todo = todo[:limit]

    if show:
        print("Articles found:", len(articles))
        print("Already have a", method, "result:", len(done))
        print("To analyze now:", len(todo))

    # load the model before the loop, so a model that can't load
    # stops the run with a clear error instead of failing every article
    if todo:
        if method in ("roberta_news", "roberta_news_v2"):
            load_roberta()
        else:
            load_vader()

    rows = []
    failed = []

    for number, article in enumerate(todo, start=1):
        try:
            sentiment, confidence = label_article(article["clean_content"], method, article.get("title"))
        except Exception as error:
            # a problem with this one article: skip it and keep going
            failed.append((article["id"], str(error)))
            if show:
                print(number, "of", len(todo), "| Article", article["id"], "| FAILED:", error)
            continue

        rows.append({
            "article_id": article["id"],
            "sentiment": sentiment,
            "confidence": round(confidence, DECIMALS),
            "method": method
        })

        if show:
            print(number, "of", len(todo), "| Article", article["id"], "|", sentiment, round(confidence, DECIMALS))

    # if there was work to do and every article failed, something is wrong
    if todo and not rows:
        raise RuntimeError("Sentiment failed on all " + str(len(todo)) + " articles. First error: " + failed[0][1])

    saved = 0
    if save and rows:
        saved = save_results(database, rows)

    return {
        "processed": saved,
        "analyzed": len(rows),
        "skipped_existing": len(done),
        "failed": len(failed),
        "failed_ids": [article_id for article_id, reason in failed],
        "low_confidence": sum(1 for row in rows if row["confidence"] < LOW_CONFIDENCE),
        "method": method
    }


if __name__ == "__main__":
    arguments = sys.argv[1:]
    method = "roberta_news"
    if "--vader" in arguments:
        method = "vader"
    elif "--v2" in arguments:
        method = "roberta_news_v2"

    if "--test" in arguments:
        count = int(arguments[arguments.index("--test") + 1])
        summary = run_sentiment(method=method, save=False, limit=count, show=True)
        print("\nTest only. Nothing was saved.")
        print(summary)

    elif "--save" in arguments:
        summary = run_sentiment(method=method, save=True, show=True)
        print("\nSaved", summary["processed"], "new rows to sentiment_results.")
        print(summary)

    else:
        database = get_database()
        articles = load_articles(database)
        done = find_done(database, [a["id"] for a in articles], method)
        print("Relevant articles (duplicates removed):", len(articles))
        print("Already have a", method, "result:", len(done))
        print("Would analyze:", len(articles) - len(done))
        print("\nNothing was analyzed or saved. Use --test 3 to try it, or --save to run it.")
