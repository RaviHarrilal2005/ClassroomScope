"""
Checking the stance labels against a person's labels.

The stance agent's labels have never been checked. This kit does the check:

  sample  draws a reproducible random sample of the articles that have a
          stance and writes a CSV for a person to label by hand. The CSV
          has no model stance, so the labeller is not swayed by it.
  score   reads the labelled CSV back and compares each human label with
          the model's: accuracy, Cohen's kappa, a confusion matrix.

Both only read Supabase (through the corpus reader). From the backend folder:
    python -m agents.stance.validation sample --n 50 --out stance_sample.csv
    python -m agents.stance.validation score stance_sample_labelled.csv
"""
import argparse
import csv
import random
from collections import Counter

from orchestrator.corpus import read_corpus

from ..supabase_client import get_client
from .stance_agent import STANCES

EXCERPT_CHARS = 600
COLUMNS = ["article_id", "title", "source", "url", "excerpt", "human_stance"]


def sample_articles(articles, n=50, seed=42):
    """A reproducible random sample of the articles that have a stance (all of them if fewer than n)."""
    labelled = sorted((a for a in articles if a.get("stance")), key=lambda a: a["id"])
    return random.Random(seed).sample(labelled, min(n, len(labelled)))


def write_sample_csv(sample, path):
    """One row per article. human_stance is left empty for the person to fill in."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for article in sample:
            writer.writerow({
                "article_id": article["id"],
                "title": article.get("title") or "",
                "source": article.get("source") or "",
                "url": article.get("url") or "",
                "excerpt": " ".join((article.get("clean_content") or "").split())[:EXCERPT_CHARS],
                "human_stance": "",
            })


def cohens_kappa(human, model):
    """
    Cohen's kappa: the agreement of two labellers beyond what chance gives.

    kappa = (p_o - p_e) / (1 - p_e). p_o is the share of items they label the
    same; p_e is the agreement that labellers with these label frequencies
    would reach by chance. Degenerate case: if p_e is 1 (both used one and the
    same label throughout), 1 - p_e is 0, but p_o is 1 too, so kappa is 1.0.
    """
    if len(human) != len(model) or not human:
        raise ValueError("Need two non-empty label lists of the same length.")
    for label in list(human) + list(model):
        if label not in STANCES:
            raise ValueError("Unknown stance label: " + str(label))
    n = len(human)
    p_o = sum(h == m for h, m in zip(human, model)) / n
    human_counts, model_counts = Counter(human), Counter(model)
    p_e = sum(human_counts[s] * model_counts[s] for s in STANCES) / (n * n)
    if p_e == 1:
        return 1.0
    return (p_o - p_e) / (1 - p_e)


def score(labelled_csv_path, articles):
    """
    Compare a person's labels in the filled CSV with the model's stance in `articles`.

    Rows with a blank or unknown human_stance, or whose article has no model
    stance, are not compared; they are counted and reported. The matrix has
    human labels as rows and model labels as columns.
    """
    model = {str(a["id"]): a["stance"] for a in articles if a.get("stance")}
    result = {"blank": 0, "unknown": 0, "no_model_stance": 0}
    pairs = []
    with open(labelled_csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            human = (row.get("human_stance") or "").strip().lower()
            if not human:
                result["blank"] += 1
            elif human not in STANCES:
                result["unknown"] += 1
            elif str(row["article_id"]).strip() not in model:
                result["no_model_stance"] += 1
            else:
                pairs.append((human, model[str(row["article_id"]).strip()]))

    matrix = {h: {m: 0 for m in STANCES} for h in STANCES}
    for human, model_label in pairs:
        matrix[human][model_label] += 1
    humans = [h for h, _ in pairs]
    models = [m for _, m in pairs]
    result.update(
        compared=len(pairs),
        accuracy=sum(h == m for h, m in pairs) / len(pairs) if pairs else None,
        kappa=cohens_kappa(humans, models) if pairs else None,
        matrix=matrix,
        human_counts={s: humans.count(s) for s in STANCES},
        model_counts={s: models.count(s) for s in STANCES},
    )
    return result


def print_report(result):
    print("Compared", result["compared"], "articles.")
    print("Skipped:", result["blank"], "blank human_stance,", result["unknown"], "unknown label,",
          result["no_model_stance"], "with no model stance.")
    if not result["compared"]:
        print("Nothing to score.")
        return
    print("Accuracy:", round(result["accuracy"], 3))
    print("Cohen's kappa:", round(result["kappa"], 3))
    print("\nConfusion matrix (rows human, columns model)")
    print(" " * 10 + "".join(s.ljust(9) for s in STANCES))
    for h in STANCES:
        print(h.ljust(10) + "".join(str(result["matrix"][h][m]).ljust(9) for m in STANCES))
    print("\nPer class (human, model):")
    for s in STANCES:
        print(" ", s.ljust(8), result["human_counts"][s], result["model_counts"][s])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the stance labels against a person's labels.")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="write a random sample to label by hand")
    sample.add_argument("--n", type=int, default=50)
    sample.add_argument("--out", default="stance_sample.csv")
    check = commands.add_parser("score", help="score a filled-in sample")
    check.add_argument("labelled_csv")
    args = parser.parse_args(argv)

    articles = read_corpus(get_client())  # SELECT only
    if args.command == "sample":
        chosen = sample_articles(articles, n=args.n)
        write_sample_csv(chosen, args.out)
        print("Wrote", len(chosen), "articles to", args.out, "with human_stance left empty.")
    else:
        print_report(score(args.labelled_csv, articles))


if __name__ == "__main__":
    main()
