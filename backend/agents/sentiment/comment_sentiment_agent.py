"""
Comment sentiment agent.

Labels each Guardian comment as positive, neutral or negative, with a
confidence score.

  model:   Hartmann 3-class RoBERTa (j-hartmann/sentiment-roberta-large-english-3-classes)
  method:  "hartmann_3"

Reads comments from the Supabase `comments` table and writes rows to
`comment_sentiment_results` (comment_id, article_id, sentiment, confidence, method).

In the pipeline:
    from agents.sentiment.comment_sentiment_agent import CommentSentimentAgent
    CommentSentimentAgent().run(ctx)     # labels the comments of ctx.approved_ids

By itself (from the backend folder, or with the run button):
    python -m agents.sentiment.comment_sentiment_agent            # shows what it would do, saves nothing
    python -m agents.sentiment.comment_sentiment_agent --test 5   # labels 5 comments and prints them, saves nothing
    python -m agents.sentiment.comment_sentiment_agent --save     # labels comments with no result yet and saves them

Only comments on relevant articles are labeled (llm_relevant = true AND
processing_status = success), and only comments that passed security
screening (screened = true, quarantined = false).

Results are saved as the run goes (every 256 comments), so stopping the run
loses nothing. Running it again picks up where it stopped.

Nothing is loaded or read when this file is imported. The model loads the
first time it is needed.
"""
import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.agents import Agent
else:
    try:
        from orchestrator.agents import Agent
    except ImportError:
        # running this file by itself, outside the team's repo: a plain stand-in
        class Agent:
            pass

MODEL_NAME = "j-hartmann/sentiment-roberta-large-english-3-classes"
METHOD = "hartmann_3"
VALID = ("positive", "neutral", "negative")

# a 512-token limit is about 2,500 characters, so cutting at 5,000 never loses anything useful
MAX_CHARS = 5000

# comments given to the model at once (lower this if memory runs out)
MODEL_BATCH = 16

# comments scored and saved together
WINDOW = 256

# rows per request when reading comments, and ids per request when checking
PAGE = 1000
BATCH = 200

# decimal places for the confidence score that gets saved
DECIMALS = 3

# results below this confidence are less reliable (counted in the summary)
LOW_CONFIDENCE = 0.6

# the model is loaded once, the first time it is needed
_classifier = None


# ---------------- model ----------------

def _build_classifier(device):
    from transformers import pipeline

    return pipeline("text-classification", model=MODEL_NAME, device=device,
                    truncation=True, max_length=512)


def label_texts(classifier, texts):
    """
    Returns [(label, confidence, error)] for each text.

    If a batch fails (memory, one bad comment, an odd label), it is split in
    half and retried, so one bad comment never stops the run.
    """
    try:
        out = []
        for result in classifier(texts):
            label = str(result["label"]).lower()
            if label not in VALID:
                raise ValueError("Model gave an unexpected label: " + str(result["label"]))
            out.append((label, float(result["score"]), ""))
        if len(out) != len(texts):
            raise RuntimeError("Model returned the wrong number of results")
        return out
    except KeyboardInterrupt:
        raise
    except Exception as error:
        if len(texts) == 1:
            return [(None, 0.0, (type(error).__name__ + ": " + str(error))[:300])]
        middle = len(texts) // 2
        return label_texts(classifier, texts[:middle]) + label_texts(classifier, texts[middle:])


def _sanity_check(classifier):
    """Three quick checks, so a wrong setup fails in seconds and not after a long run."""
    tests = [("I love this, it is wonderful and I am so happy.", "positive"),
             ("This is terrible, awful and a complete disgrace.", "negative"),
             ("The meeting is held on Tuesday at noon.", "neutral")]
    results = label_texts(classifier, [text for text, wanted in tests])
    for (text, wanted), (label, confidence, error) in zip(tests, results):
        if error:
            return False, "model error: " + error
        if label != wanted:
            return False, "sanity check gave '" + str(label) + "' for '" + text + "' (expected '" + wanted + "')"
    return True, "ok"


def load_classifier():
    global _classifier
    if _classifier is None:
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        import torch

        if torch.cuda.is_available():
            device = 0
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = -1

        classifier = _build_classifier(device)
        ok, why = _sanity_check(classifier)
        if not ok and device != -1:
            # the GPU gave odd answers: use the CPU, which is slower but safe
            classifier = _build_classifier(-1)
            ok, why = _sanity_check(classifier)
        if not ok:
            raise RuntimeError("Comment sentiment model failed its sanity check: " + why)
        _classifier = classifier
    return _classifier


# ---------------- database ----------------

def get_database():
    # in the pipeline, use the client the whole team shares
    try:
        from ..supabase_client import get_client

        return get_client()
    except ImportError:
        pass

    # when this file is run by itself, connect using the .env file
    from dotenv import load_dotenv
    from supabase import create_client

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_KEY is missing from the .env file")
    return create_client(url, key)


def relevant_article_ids(database, article_ids=None):
    """
    Ids of the relevant, successfully cleaned articles.

    Relevant means Juan's rule: llm_relevant = true AND processing_status = success.

    article_ids  only these articles (the pipeline passes ctx.approved_ids).
                 None means every relevant article.
    """
    found = []

    if article_ids is not None:
        wanted = list(article_ids)
        for start in range(0, len(wanted), BATCH):
            response = (
                database.table("articles")
                .select("id")
                .in_("id", wanted[start:start + BATCH])
                .eq("llm_relevant", True)
                .eq("processing_status", "success")
                .execute()
            )
            found.extend(row["id"] for row in (response.data or []))
    else:
        start = 0
        while True:
            response = (
                database.table("articles")
                .select("id")
                .eq("llm_relevant", True)
                .eq("processing_status", "success")
                .order("id")
                .range(start, start + PAGE - 1)
                .execute()
            )
            page = response.data or []
            found.extend(row["id"] for row in page)
            if len(page) < PAGE:
                break
            start += PAGE

    return sorted(set(found))


def load_comments(database, article_ids):
    """
    Screened, not quarantined comments on these articles, without duplicates
    and without empty text. Text longer than MAX_CHARS is cut.
    """
    comments = []
    seen = set()

    for article_id in article_ids:
        start = 0
        while True:
            response = (
                database.table("comments")
                .select("comment_id, article_id, body_text")
                .eq("article_id", article_id)
                .eq("screened", True)
                .eq("quarantined", False)
                .order("comment_id")
                .range(start, start + PAGE - 1)
                .execute()
            )
            page = response.data or []
            for row in page:
                comment_id = row["comment_id"]
                text = (row.get("body_text") or "").strip()
                if comment_id in seen or text == "":
                    continue
                seen.add(comment_id)
                comments.append({"comment_id": comment_id,
                                 "article_id": row["article_id"],
                                 "body_text": text[:MAX_CHARS]})
            if len(page) < PAGE:
                break
            start += PAGE

    return comments


def find_done(database, comment_ids, method=METHOD):
    """Comment ids that already have a result from this method."""
    done = set()
    ids = list(comment_ids)
    for start in range(0, len(ids), BATCH):
        response = (
            database.table("comment_sentiment_results")
            .select("comment_id")
            .in_("comment_id", ids[start:start + BATCH])
            .eq("method", method)
            .execute()
        )
        # the results table stores comment_id as bigint, comments as text:
        # compare as strings, or nothing ever counts as done
        for row in response.data or []:
            done.add(str(row["comment_id"]))
    return done


def save_results(database, rows):
    """
    Add new rows to comment_sentiment_results. Never changes or deletes existing rows.

    Checks again right before saving, so two runs at the same time
    do not write the same comment twice.
    """
    if not rows:
        return 0

    by_method = {}
    for row in rows:
        by_method.setdefault(row["method"], []).append(row)

    new_rows = []
    for method, group in by_method.items():
        done = find_done(database, [row["comment_id"] for row in group], method)
        new_rows.extend(row for row in group if row["comment_id"] not in done)

    for start in range(0, len(new_rows), BATCH):
        database.table("comment_sentiment_results").insert(new_rows[start:start + BATCH]).execute()
    return len(new_rows)


# ---------------- the agent ----------------

class CommentSentimentAgent(Agent):
    """
    Pipeline agent. run(ctx) labels the comments on the approved articles
    that do not have a result yet and writes them to comment_sentiment_results.
    """

    name = "comment_sentiment"

    def run(self, ctx):
        return run_comment_sentiment(article_ids=ctx.approved_ids, save=True)


def run_comment_sentiment(article_ids=None, save=True, limit=None, show=False, batch=MODEL_BATCH):
    """
    Label comments and (if save is True) write the results.

    Returns a summary dict. Raises an error if something goes wrong, so
    the pipeline coordinator can see the failure. It does not retry.
    """
    summary = {"processed": 0, "analyzed": 0, "skipped_existing": 0, "failed": 0,
               "failed_ids": [], "low_confidence": 0, "method": METHOD}

    # the pipeline gave no articles: nothing to do, and no need to load the model
    if article_ids is not None and len(article_ids) == 0:
        return summary

    database = get_database()

    article_ids = relevant_article_ids(database, article_ids)
    comments = load_comments(database, article_ids)
    done = find_done(database, [c["comment_id"] for c in comments])
    todo = [c for c in comments if c["comment_id"] not in done]
    summary["skipped_existing"] = len(done)

    if limit is not None:
        todo = todo[:limit]

    if show:
        print("Relevant articles:", len(article_ids))
        print("Comments found:", len(comments))
        print("Already have a", METHOD, "result:", len(done))
        print("To analyze now:", len(todo))

    if not todo:
        return summary

    # load the model before the loop, so a model that can't load
    # stops the run with a clear error instead of failing every comment
    classifier = load_classifier()

    first_error = ""
    for window_start in range(0, len(todo), WINDOW):
        # sort by length inside the window, so short comments are not padded to long ones
        window = sorted(todo[window_start:window_start + WINDOW], key=lambda c: len(c["body_text"]))
        rows = []

        for start in range(0, len(window), batch):
            chunk = window[start:start + batch]
            results = label_texts(classifier, [c["body_text"] for c in chunk])
            for comment, (label, confidence, error) in zip(chunk, results):
                if error:
                    summary["failed"] += 1
                    summary["failed_ids"].append(comment["comment_id"])
                    first_error = first_error or error
                    if show:
                        print("Comment", comment["comment_id"], "| FAILED:", error)
                    continue
                rows.append({
                    "comment_id": comment["comment_id"],
                    "article_id": comment["article_id"],
                    "sentiment": label,
                    "confidence": round(confidence, DECIMALS),
                    "method": METHOD
                })
                if show:
                    print("Comment", comment["comment_id"], "|", label, round(confidence, DECIMALS))

        summary["analyzed"] += len(rows)
        summary["low_confidence"] += sum(1 for row in rows if row["confidence"] < LOW_CONFIDENCE)
        if save and rows:
            summary["processed"] += save_results(database, rows)

        if show and not limit:
            print("  done", min(window_start + WINDOW, len(todo)), "of", len(todo))

    # if every comment failed (and there were enough to be sure), the model or the
    # setup is broken: stop with an error. A few stuck comments are only reported
    # in failed_ids, so they do not fail the pipeline on every run.
    if summary["analyzed"] == 0 and len(todo) >= 5:
        raise RuntimeError("Comment sentiment failed on all " + str(len(todo)) + " comments. First error: " + first_error)

    return summary


if __name__ == "__main__":
    arguments = sys.argv[1:]

    if "--test" in arguments:
        count = int(arguments[arguments.index("--test") + 1])
        result = run_comment_sentiment(save=False, limit=count, show=True)
        print("\nTest only. Nothing was saved.")
        print(result)

    elif "--save" in arguments:
        result = run_comment_sentiment(save=True, show=True)
        print("\nSaved", result["processed"], "new rows to comment_sentiment_results.")
        print(result)

    else:
        database = get_database()
        article_ids = relevant_article_ids(database)
        comments = load_comments(database, article_ids)
        done = find_done(database, [c["comment_id"] for c in comments])
        print("Relevant articles:", len(article_ids))
        print("Comments on them (screened, not quarantined):", len(comments))
        print("Already have a", METHOD, "result:", len(done))
        print("Would analyze:", len(comments) - len(done))
        print("\nNothing was analyzed or saved. Use --test 5 to try it, or --save to run it.")
