"""
Stance agent.

The stance each article takes toward generative AI in education: favor,
against or neutral, the three labels of SemEval-2016 Task 6, the standard
stance-detection benchmark. Sentiment says how an article sounds; stance
says which side of the question it comes down on, which is what a
researcher comparing coverage needs.

  model:   GPT-5.6-Luna, the LLM the classification agent already uses
           (classification/classify_luna.py, which makes the call)
  method:  "gpt-5.6-luna"
  target:  TARGET, saved on every row so a later target can sit beside it

Writes rows to stance_results (article_id, stance, confidence, target,
method). The confidence is the model's own estimate, not a calibrated
probability. Articles that already have a row from this method are
skipped, so re-running costs nothing for them.

In the pipeline:
    StanceAgent().run(ctx)     # labels ctx.approved_ids

By itself (from the backend folder):
    python -m agents.stance.stance_agent --test 5   # labels 5 articles and prints them, saves nothing
    python -m agents.stance.stance_agent --save     # labels every relevant article with no stance yet
"""
import io
import sys
import time

from orchestrator.agents import Agent

from ..classification import classify_luna as luna
from ..sentiment.sentiment_agent import load_articles
from ..supabase_client import get_client

STANCES = ("favor", "against", "neutral")
TARGET = "generative AI in education"
METHOD = luna.MODEL

# seconds between LLM calls, the same pace as the classifier
CALL_INTERVAL = 0.3

# rows per request when checking or saving; results are saved every BATCH
# articles, so stopping a long run loses at most one batch
BATCH = 25

DECIMALS = 3


def build_prompt(title, content):
    return f"""You are labelling the stance of a news article toward a target.

Target: {TARGET}: students, teachers, schools and universities using tools such as ChatGPT for learning, teaching or schoolwork.

Label the article's overall stance toward the target with exactly ONE of:
- favor: on balance the article presents the target positively: its benefits, or arguments for adopting or expanding it.
- against: on balance the article presents the target negatively: its harms or risks, or arguments for restricting or banning it.
- neutral: the article is balanced between the two, purely factual, or takes no clear position.

Judge the article as a whole, by what it argues and how it frames the story, not by the view of each person it quotes. Straight reporting that gives both sides is neutral.

Article title: {title}

Article text:
{content[:8000]}

Respond with JSON only, no other text:
{{"category": "<favor, against or neutral>", "confidence": <0.0-1.0>}}"""


def label_article(title, content):
    """Returns (stance, confidence) for one article. Raises ValueError if the model gave no usable label."""
    label, confidence, error = luna.call_luna(build_prompt(title, content))
    if error:
        raise ValueError(error)
    stance = str(label).strip().lower()
    if stance not in STANCES:
        raise ValueError("Model gave an unexpected stance: " + str(label))
    return stance, float(confidence or 0.0)


def find_done(database, article_ids):
    """Article ids that already have a stance from this method."""
    done = set()
    ids = list(article_ids)
    for start in range(0, len(ids), BATCH):
        response = (
            database.table("stance_results")
            .select("article_id")
            .in_("article_id", ids[start:start + BATCH])
            .eq("method", METHOD)
            .execute()
        )
        done.update(row["article_id"] for row in response.data or [])
    return done


def run_stance(article_ids=None, save=True, limit=None, show=False, call_interval=CALL_INTERVAL):
    """
    Label articles and (if save is True) write the results.

    article_ids  only these articles (the pipeline passes ctx.approved_ids);
                 None means every relevant article.

    Raises if every article failed (an outage or a bad key, not a result),
    so the coordinator can retry. It does not retry by itself.
    """
    summary = {"processed": 0, "analyzed": 0, "skipped_existing": 0, "failed": 0,
               "failed_ids": [], "method": METHOD}
    if article_ids is not None and len(article_ids) == 0:
        return summary

    database = get_client()
    articles = load_articles(database, article_ids)
    done = find_done(database, [a["id"] for a in articles])
    todo = [a for a in articles if a["id"] not in done]
    summary["skipped_existing"] = len(done)
    if limit is not None:
        todo = todo[:limit]

    rows, first_error = [], ""
    for number, article in enumerate(todo, start=1):
        if number > 1:
            time.sleep(call_interval)
        try:
            stance, confidence = label_article(article.get("title"), article["clean_content"])
        except Exception as error:
            summary["failed"] += 1
            summary["failed_ids"].append(article["id"])
            first_error = first_error or str(error)
            if show:
                print(number, "of", len(todo), "| Article", article["id"], "| FAILED:", error)
            continue

        rows.append({"article_id": article["id"], "stance": stance,
                     "confidence": round(confidence, DECIMALS), "target": TARGET, "method": METHOD})
        summary["analyzed"] += 1
        if show:
            print(number, "of", len(todo), "| Article", article["id"], "|", stance, round(confidence, DECIMALS),
                  "|", (article.get("title") or "")[:70])
        if save and len(rows) == BATCH:
            database.table("stance_results").insert(rows).execute()
            summary["processed"] += len(rows)
            rows = []

    if save and rows:
        database.table("stance_results").insert(rows).execute()
        summary["processed"] += len(rows)

    if todo and summary["analyzed"] == 0:
        raise RuntimeError("Stance failed on all " + str(len(todo)) + " articles. First error: " + first_error)
    return summary


class StanceAgent(Agent):
    """Pipeline agent: labels the approved articles that have no stance yet."""

    name = "stance_luna"

    def run(self, ctx):
        if not luna.API_KEY or not luna.BASE_URL:
            raise RuntimeError("The stance agent needs TRUSSED_API_KEY and TRUSSED_BASE_URL in backend/.env")
        return run_stance(article_ids=ctx.approved_ids)


if __name__ == "__main__":
    # A Windows console can't show every character in a headline; a "?" beats a crash mid-run.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    arguments = sys.argv[1:]
    if "--test" in arguments:
        count = int(arguments[arguments.index("--test") + 1])
        print(run_stance(save=False, limit=count, show=True))
        print("\nTest only. Nothing was saved.")
    elif "--save" in arguments:
        result = run_stance(save=True, show=True)
        print("\nSaved", result["processed"], "new rows to stance_results.")
        print(result)
    else:
        print(__doc__)
