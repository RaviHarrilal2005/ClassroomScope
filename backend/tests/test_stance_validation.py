"""The stance validation kit, offline: plain dict rows, no database and no network."""
import csv

import pytest

from agents.stance import validation as kit


def article(id, stance="favor", content="Schools  are\nadopting AI tutors."):
    return {"id": id, "title": f"Article {id}", "source": "Src", "url": f"https://x/{id}",
            "clean_content": content, "stance": stance}


def test_sample_is_reproducible_and_only_takes_articles_with_a_stance():
    articles = [article(i, stance=None if i % 4 == 0 else "against") for i in range(1, 41)]
    first = kit.sample_articles(articles, n=10)
    assert [a["id"] for a in first] == [a["id"] for a in kit.sample_articles(articles, n=10)]
    assert len(first) == 10 and all(a["stance"] for a in first)
    assert len(kit.sample_articles(articles[:3], n=50)) == 3  # fewer labelled articles than n: take them all


def test_sample_csv_has_no_model_stance_and_an_empty_human_column(tmp_path):
    path = tmp_path / "sample.csv"
    kit.write_sample_csv([article(1, content="word " * 300)], str(path))
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == kit.COLUMNS
    assert rows[0]["human_stance"] == ""
    assert len(rows[0]["excerpt"]) == kit.EXCERPT_CHARS and "\n" not in rows[0]["excerpt"]


def test_kappa_matches_the_hand_worked_example():
    # 6 articles; they agree on 1, 3, 4 and 6, so p_o = 4/6.
    # Human counts: favor 2, against 1, neutral 3. Model counts: favor 2, against 2, neutral 2.
    # p_e = (2*2 + 1*2 + 3*2) / 6**2 = 12/36 = 1/3.
    # kappa = (4/6 - 1/3) / (1 - 1/3) = (1/3) / (2/3) = 0.5
    human = ["favor", "favor", "against", "neutral", "neutral", "neutral"]
    model = ["favor", "against", "against", "neutral", "favor", "neutral"]
    assert kit.cohens_kappa(human, model) == pytest.approx(0.5)


def test_degenerate_case_one_label_everywhere_is_perfect_agreement():
    # p_e is 1, so 1 - p_e is 0 and the formula would divide by zero; kappa is defined as 1.0.
    assert kit.cohens_kappa(["favor"] * 3, ["favor"] * 3) == 1.0


def test_score_ignores_blank_and_unknown_rows_and_counts_them(tmp_path):
    path = tmp_path / "labelled.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(kit.COLUMNS)
        writer.writerow([1, "t", "s", "u", "e", "favor"])
        writer.writerow([2, "t", "s", "u", "e", ""])
        writer.writerow([3, "t", "s", "u", "e", "maybe"])
        writer.writerow([4, "t", "s", "u", "e", "against"])
        writer.writerow([9, "t", "s", "u", "e", "neutral"])  # no model stance for this id
    articles = [article(1, "favor"), article(2, "against"), article(3, "neutral"), article(4, "favor")]
    result = kit.score(str(path), articles)
    assert (result["compared"], result["blank"], result["unknown"], result["no_model_stance"]) == (2, 1, 1, 1)
    assert result["accuracy"] == 0.5


def test_confusion_matrix_has_human_as_rows_and_model_as_columns(tmp_path):
    path = tmp_path / "labelled.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(kit.COLUMNS)
        writer.writerow([1, "t", "s", "u", "e", "against"])  # human says against, model says favor
    result = kit.score(str(path), [article(1, "favor")])
    assert result["matrix"]["against"]["favor"] == 1
    assert result["matrix"]["favor"]["against"] == 0
