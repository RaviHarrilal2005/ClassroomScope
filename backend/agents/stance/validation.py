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
import os
import random
from collections import Counter

from orchestrator.corpus import read_corpus

from ..supabase_client import get_client
from .stance_agent import STANCES

EXCERPT_CHARS = 600
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
COLUMNS = ["article_id", "title", "source", "url", "excerpt", "human_stance"]


def sample_articles(articles, n=50, seed=42):
    """A reproducible random sample of the articles that have a stance (all of them if fewer than n)."""
    labelled = sorted((a for a in articles if a.get("stance")), key=lambda a: a["id"])
    return random.Random(seed).sample(labelled, min(n, len(labelled)))


def _cell(text):
    """Text from news sites is untrusted: one starting with = + - @ would run as a formula in a
    spreadsheet, so it gets a leading apostrophe, as in frontend/src/csv.js."""
    return "'" + text if text.startswith(_FORMULA_START) else text


def write_sample_csv(sample, path):
    """One row per article. human_stance is left empty for the person to fill in."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for article in sample:
            writer.writerow({
                "article_id": article["id"],
                "title": _cell(article.get("title") or ""),
                "source": _cell(article.get("source") or ""),
                "url": _cell(article.get("url") or ""),
                "excerpt": _cell(" ".join((article.get("clean_content") or "").split())[:EXCERPT_CHARS]),
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


def read_labelled_rows(path):
    """
    The rows of the filled-in CSV. Excel's plain "CSV (Comma delimited)" is cp1252, not
    UTF-8, and a ; list separator gives a semicolon-separated file: read both.
    """
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    header = text.split("\n", 1)[0]
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    missing = {"article_id", "human_stance"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"{path} has no {' or '.join(sorted(missing))} column; use the file from `sample`, saved as CSV UTF-8.")
    return list(reader)


def score(labelled_csv_path, articles):
    """
    Compare a person's labels in the filled CSV with the model's stance in `articles`.

    Rows with a blank or unknown human_stance, or whose article has no model
    stance, are not compared; they are counted and reported (unknown labels
    by value, so "for" or "favour" can be fixed), and a repeated article_id
    counts once. The matrix has human labels as rows and model labels as columns.
    """
    model = {str(a["id"]): a["stance"] for a in articles if a.get("stance") in STANCES}
    result = {"blank": 0, "unknown": 0, "no_model_stance": 0, "duplicate": 0, "unknown_labels": []}
    pairs = []
    seen = set()
    for row in read_labelled_rows(labelled_csv_path):
        article_id = str(row["article_id"]).strip()
        human = (row.get("human_stance") or "").strip().lower()
        if article_id in seen:
            result["duplicate"] += 1
        elif not human:
            result["blank"] += 1
        elif human not in STANCES:
            result["unknown"] += 1
            result["unknown_labels"].append((article_id, human))
        elif article_id not in model:
            result["no_model_stance"] += 1
        else:
            pairs.append((human, model[article_id]))
        seen.add(article_id)

    matrix = {h: {m: 0 for m in STANCES} for h in STANCES}
    for human, model_label in pairs:
        matrix[human][model_label] += 1
    humans = [h for h, _ in pairs]
    models = [m for _, m in pairs]
    result.update(
        compared=len(pairs),
        accuracy=sum(h == m for h, m in pairs) / len(pairs) if pairs else None,
        kappa=cohens_kappa(humans, models) if pairs else None,
        # p_e == 1: one label throughout, kappa is undefined (cohens_kappa returns 1.0)
        kappa_undefined=bool(pairs) and len(set(humans)) == 1 and set(humans) == set(models),
        matrix=matrix,
        human_counts={s: humans.count(s) for s in STANCES},
        model_counts={s: models.count(s) for s in STANCES},
    )
    return result


def print_report(result):
    print("Compared", result["compared"], "articles.")
    print("Skipped:", result["blank"], "blank human_stance,", result["unknown"], "unknown label,",
          result["no_model_stance"], "with no model stance,", result["duplicate"], "repeated article_id.")
    if result["unknown_labels"]:
        print("Unknown labels (use favor, against or neutral):",
              ", ".join(f"{i}: {v!r}" for i, v in result["unknown_labels"]))
    if not result["compared"]:
        print("Nothing to score.")
        return
    print("Accuracy:", round(result["accuracy"], 3))
    print("Cohen's kappa:", "undefined (one label throughout)" if result["kappa_undefined"] else round(result["kappa"], 3))
    print("\nConfusion matrix (rows human, columns model)")
    print(" " * 10 + "".join(s.ljust(9) for s in STANCES))
    for h in STANCES:
        print(h.ljust(10) + "".join(str(result["matrix"][h][m]).ljust(9) for m in STANCES))
    print("\nPer class (human, model):")
    for s in STANCES:
        print(" ", s.ljust(8), result["human_counts"][s], result["model_counts"][s])


def _positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the stance labels against a person's labels.")
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("sample", help="write a random sample to label by hand")
    sample.add_argument("--n", type=_positive_int, default=50)
    sample.add_argument("--out", default="stance_sample.csv")
    check = commands.add_parser("score", help="score a filled-in sample")
    check.add_argument("labelled_csv")
    args = parser.parse_args(argv)

    if args.command == "sample" and os.path.exists(args.out):
        parser.error(f"{args.out} already exists (it may hold labels): choose another --out or move it")
    articles = read_corpus(get_client())  # SELECT only
    if args.command == "sample":
        chosen = sample_articles(articles, n=args.n)
        write_sample_csv(chosen, args.out)
        print("Wrote", len(chosen), "articles to", args.out, "with human_stance left empty.")
    else:
        print_report(score(args.labelled_csv, articles))


if __name__ == "__main__":
    main()
