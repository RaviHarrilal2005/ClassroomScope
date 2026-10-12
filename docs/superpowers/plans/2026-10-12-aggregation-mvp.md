# Aggregation MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /api/v1/results` serves figures computed from the real analysis tables (sentiment, topic, classification) instead of the hardcoded stub, including the three breakdowns the demo reviewers asked for: sentiment over time, by topic, and by stakeholder.

**Architecture:** One pure module (`compute.py`) turns table rows into the dashboard payload. `results.py` pages the four tables and recomputes on each request, the same way `orchestrator/topic_counts.py` already does for topics (its reader is replaced and deleted). The pipeline's aggregation stage runs the same computation once per run, so a broken table fails the stage loudly instead of only breaking the page. No new table, no migration, no snapshot.

**Tech Stack:** Python 3.13, Flask 3.0, supabase-py (PostgREST), pytest, pyright, React 18 (Vite). No new dependencies.

**Spec:** [`docs/pipeline-coordinator.md`](../../pipeline-coordinator.md) (the agent contract, "For agent owners: plugging in your agent") and the payload described by `get_results()` in [`backend/app.py`](../../../backend/app.py). It supersedes [`2026-09-29-aggregation-agent.md`](2026-09-29-aggregation-agent.md), which was written before sentiment existed and assumes a snapshot table, a `ResultsStore` and a `sentiment_label` column. The real column is `sentiment`. There is no standalone written spec, so the decisions below are this plan's own and need a reviewer's yes before work starts.

**Prerequisites (separate PRs, already on branches):** `fix-quarantine-logging` (two currently failing tests) and `wire-sentiment-agent` (sentiment in the pipeline). This plan does not depend on either's code, but its end-to-end check expects `sentiment_results` to be filled by the pipeline.

## Global Constraints

- **`orchestrator/` never imports an agent.** `agents/adapters.py` is the one file that knows both sides. `agents/aggregation/` may import from `orchestrator/` (`topic_counts.top_topics`), never the reverse.
- **Agents raise on failure and never retry internally.** Retry counts live in `orchestrator/retry.py`; aggregation's policy is untouched.
- **Read through `agents/supabase_client.get_client()`.** Never build another client, never call `load_dotenv()` at import time.
- **The test suite never touches the network.** It passes `live=False` and behaves the same with or without `backend/.env`.
- **`python -m pyright backend/` stays clean** (run from the repo root). `agents/aggregation` is not added to `exclude`.
- **No invented numbers.** Anything that cannot be computed is reported as missing, with a reason, never as a zero that reads like a finding.
- **Payload contract is additive.** `sentiment_distribution`, `top_topics` and `articles` keep their current names and shapes so the existing charts keep working.

## Review Focus

Most likely to bite first. Each line's test is added to the task named.

1. **PostgREST caps a request at 1000 rows.** `articles` has 2,416 rows today. A reader that trusts one request aggregates a subset and publishes it as the whole picture, with no error. → paging test, **Task 2**.
2. **Two classifier rows per article.** `classification_results` has 823 rows over about 437 articles (386 have both the keyword and the LLM row). Counting the table directly double-counts them. → `pick_one` test, **Task 1**.
3. **Two sentiment methods per article** once VADER runs as a fallback. Both rows must not count. → `pick_one` test, **Task 1**.
4. **An article with sentiment but no topic or stakeholder yet.** It belongs in the totals and the timeline, is left out of the by-topic breakdown, and shows as `undetermined` in the table. It must not raise. → **Task 1**.
5. **Empty or unreadable data** (a fresh database, a table that errors) must give a valid payload with `analysed: 0`, not a `ZeroDivisionError` or a 500, from the endpoint. The pipeline stage must still raise. → **Tasks 1, 3, 4**.

## Design decisions this plan makes

1. **Recompute on request, no snapshot table, no cache.** Measured against the real database: 1.6 s per request, which is eight sequential round trips of 0.1-0.2 s (four tables, each read until an empty page). The dashboard loads `/results` once on open, so that is acceptable for the MVP. A snapshot needs a manual migration (the remote history cannot take `supabase db push`) and a `ResultsStore`. Upgrade path, cheapest first: read the four tables on threads (about 0.4 s), then a 60 s in-process cache, then a snapshot row. Add one when the page feels slow or a filter UI needs per-filter numbers. The code carries a `ponytail:` comment saying so.
2. **The corpus is "articles that have a sentiment result".** Not `llm_relevant` alone: 328 articles pass the relevance rule but 323 have results (duplicates are skipped by content hash). Counting the other 5 would deflate every share.
3. **Aggregation reads the whole corpus, not `ctx.approved_ids`.** The dashboard shows the state of the corpus; a run that collected 40 articles must not replace a 323-article picture with a 40-article one.
4. **Preference order when an article has several rows.** Sentiment: `roberta_news` over `vader`. Stakeholder: any LLM classifier over `baseline_keyword`.
5. **Months, not weeks.** Dates run 2022-11 to 2026-10; weekly buckets would be mostly empty.
6. **`stance_results` is not read.** The table is empty and nothing on the dashboard uses it.

---

## File Structure

**New**
- `backend/agents/aggregation/__init__.py`: empty package marker.
- `backend/agents/aggregation/compute.py`: pure functions, no database, no clock. Holds every counting rule so it can be tested without a fake client.
- `backend/agents/aggregation/results.py`: `read_all` (paged read), `read_corpus` (the four tables), `compute_results(client)` (raises) and `reader(client)` / `reader_from_env()` for the endpoint (never raises).
- `backend/tests/test_aggregation.py`: all aggregation tests, one file.

**Modified**
- `backend/agents/adapters.py`: `AggregationAgent`.
- `backend/orchestrator/registry.py`: register it where live.
- `backend/app.py`: `read_results` replaces `read_topics` and the hardcoded payload.
- `backend/orchestrator/topic_counts.py`: delete `read_topic_rows`, `reader`, `reader_from_env` (no callers once `/results` moves; `read_all` replaces the paging). Keep `top_topics` and `unavailable`.
- `backend/tests/helpers.py`, `backend/tests/test_topic_counts.py`, `backend/tests/test_registry_wiring.py`: follow the rename, drop the deleted reader's tests, and the new real stage.
- `frontend/src/components/DashboardShell.jsx`: drop the two "placeholder" notes that become false.
- `README.md`, `NEXT_STEPS.md`, `docs/pipeline-coordinator.md`: stage is real now.

---

### Task 1: The counting rules

**Files:**
- Create: `backend/agents/aggregation/__init__.py`, `backend/agents/aggregation/compute.py`
- Test: `backend/tests/test_aggregation.py`

**Interfaces:**
- Consumes: `orchestrator.topic_counts.top_topics(rows) -> facet dict` (rows need `stable_topic_id`, `topic`).
- Produces:
  - `pick_one(rows: list[dict], rank: Callable[[dict], Any]) -> dict[int, dict]`: the lowest-`rank` row per `article_id`.
  - `build_results(articles, sentiment_rows, topic_rows, class_rows, max_articles=100) -> dict` with keys `analysed`, `sentiment_distribution`, `top_topics`, `sentiment_over_time`, `sentiment_by_topic`, `sentiment_by_stakeholder`, `articles`, `error`.
  - `empty_results(reason: str) -> dict`: the same keys, all empty, `error` set.
  - Row shapes `articles`: `id, title, source, published_date, url`; `sentiment_rows`: `article_id, sentiment, method`; `topic_rows`: `article_id, stable_topic_id, topic`; `class_rows`: `article_id, classifier, stakeholder_category`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_aggregation.py
"""
The aggregation rules. What goes quietly wrong here: an article counted
twice because two methods labelled it, a missing topic raising instead of
being skipped, an empty corpus dividing by zero.
"""
from agents.aggregation.compute import build_results, empty_results, pick_one


def art(id, month="2025-03", title=None):
    return {"id": id, "title": title or f"Article {id}", "source": "EdSurge",
            "published_date": f"{month}-10T10:00:00+00:00", "url": f"https://x/{id}"}


def sent(article_id, label, method="roberta_news"):
    return {"article_id": article_id, "sentiment": label, "method": method}


def topic(article_id, stable="T001", label="Adoption"):
    return {"article_id": article_id, "stable_topic_id": stable, "topic": label}


def klass(article_id, stakeholder="educators", classifier="gpt-5.6-luna"):
    return {"article_id": article_id, "classifier": classifier, "stakeholder_category": stakeholder}


def test_pick_one_keeps_the_best_ranked_row_per_article():
    rows = [klass(1, "students", "baseline_keyword"), klass(1, "educators"), klass(2, "parents", "baseline_keyword")]
    picked = pick_one(rows, lambda r: r["classifier"] == "baseline_keyword")
    assert picked[1]["stakeholder_category"] == "educators"
    assert picked[2]["stakeholder_category"] == "parents"


def test_an_article_labelled_by_two_methods_counts_once():
    result = build_results([art(1)], [sent(1, "negative", "vader"), sent(1, "positive")], [], [])
    assert result["sentiment_distribution"] == {"positive": 1, "neutral": 0, "negative": 0}
    assert result["analysed"] == 1


def test_distribution_is_shares_of_the_analysed_articles():
    arts = [art(i) for i in range(1, 5)]
    sents = [sent(1, "positive"), sent(2, "neutral"), sent(3, "neutral"), sent(4, "negative")]
    result = build_results(arts, sents, [], [])
    assert result["sentiment_distribution"] == {"positive": 0.25, "neutral": 0.5, "negative": 0.25}


def test_articles_without_a_sentiment_result_are_not_part_of_the_corpus():
    result = build_results([art(1), art(2)], [sent(1, "positive")], [], [])
    assert result["analysed"] == 1
    assert [a["id"] for a in result["articles"]] == [1]


def test_timeline_buckets_by_month_oldest_first_and_skips_undated():
    undated = {**art(3), "published_date": None}
    arts = [art(1, "2025-03"), art(2, "2024-11"), undated]
    result = build_results(arts, [sent(1, "positive"), sent(2, "negative"), sent(3, "neutral")], [], [])
    assert [(m["label"], m["total"]) for m in result["sentiment_over_time"]] == [("2024-11", 1), ("2025-03", 1)]
    assert result["analysed"] == 3  # the undated article still counts in the totals


def test_by_topic_counts_each_topic_and_leaves_out_unassigned_articles():
    arts = [art(1), art(2), art(3)]
    sents = [sent(1, "positive"), sent(2, "negative"), sent(3, "neutral")]
    topics = [topic(1), topic(2), topic(3, stable=None, label="Unassigned")]
    rows = build_results(arts, sents, topics, [])["sentiment_by_topic"]
    assert rows == [{"label": "Adoption", "positive": 1, "neutral": 0, "negative": 1, "total": 2}]


def test_stakeholder_prefers_the_llm_row_and_defaults_to_undetermined():
    arts = [art(1), art(2)]
    sents = [sent(1, "positive"), sent(2, "negative")]
    classes = [klass(1, "students", "baseline_keyword"), klass(1, "educators")]
    by = {r["label"]: r for r in build_results(arts, sents, [], classes)["sentiment_by_stakeholder"]}
    assert by["educators"]["positive"] == 1 and "students" not in by
    assert by["undetermined"]["negative"] == 1


def test_articles_table_is_newest_first_and_capped():
    arts = [art(1, "2024-01"), art(2, "2025-06"), art(3, "2023-05")]
    sents = [sent(i, "neutral") for i in (1, 2, 3)]
    result = build_results(arts, sents, [], [], max_articles=2)
    assert [a["id"] for a in result["articles"]] == [2, 1]
    assert result["articles"][0]["stakeholder"] == "undetermined"


def test_an_empty_corpus_gives_a_valid_payload_not_an_error():
    result = build_results([], [], [], [])
    assert result["analysed"] == 0
    assert result["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 0}
    assert result["sentiment_over_time"] == [] and result["articles"] == []
    assert result["top_topics"]["available"] is False
    assert result["error"] is None


def test_empty_results_carries_the_reason():
    assert empty_results("boom")["error"] == "boom"
    assert empty_results("boom")["analysed"] == 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: collection error, `ModuleNotFoundError: agents.aggregation`.

- [ ] **Step 3: Implement**

```python
# backend/agents/aggregation/__init__.py  (empty)
```

```python
# backend/agents/aggregation/compute.py
"""
The aggregation rules, as pure functions.

No database, no network, no clock: rows in, dashboard payload out, so
every counting decision can be tested without a fake Supabase.

The corpus is the articles that have a sentiment result. When an article
has several rows in one table (two sentiment methods, two classifiers)
the best-ranked one is used, so nothing is counted twice.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from orchestrator.topic_counts import top_topics, unavailable

SENTIMENTS = ("positive", "neutral", "negative")
PREFERRED_SENTIMENT_METHOD = "roberta_news"
BASELINE_CLASSIFIER = "baseline_keyword"
UNDETERMINED = "undetermined"

Row = Dict[str, Any]


def pick_one(rows: Iterable[Row], rank: Callable[[Row], Any]) -> Dict[int, Row]:
    """The lowest-ranked row for each article_id."""
    best: Dict[int, Row] = {}
    for row in rows:
        current = best.get(row["article_id"])
        if current is None or rank(row) < rank(current):
            best[row["article_id"]] = row
    return best


def _zero_counts() -> Dict[str, int]:
    return {s: 0 for s in SENTIMENTS}


def _breakdown(pairs: Iterable[tuple], sort_by_label: bool = False) -> List[Row]:
    """pairs of (label, sentiment) -> one row per label with a count per sentiment."""
    rows: Dict[str, Row] = {}
    for label, sentiment in pairs:
        row = rows.setdefault(label, {"label": label, **_zero_counts(), "total": 0})
        row[sentiment] += 1
        row["total"] += 1
    if sort_by_label:
        return sorted(rows.values(), key=lambda r: r["label"])
    return sorted(rows.values(), key=lambda r: (-r["total"], r["label"]))


def empty_results(reason: Optional[str] = None) -> Row:
    return {
        "analysed": 0,
        "sentiment_distribution": _zero_counts(),
        "top_topics": unavailable(reason or "No topic results yet."),
        "sentiment_over_time": [],
        "sentiment_by_topic": [],
        "sentiment_by_stakeholder": [],
        "articles": [],
        "error": reason,
    }


def build_results(
    articles: Iterable[Row],
    sentiment_rows: Iterable[Row],
    topic_rows: Iterable[Row],
    class_rows: Iterable[Row],
    max_articles: int = 100,
) -> Row:
    sentiment = pick_one(sentiment_rows, lambda r: r["method"] != PREFERRED_SENTIMENT_METHOD)
    topic_rows = list(topic_rows)
    topic_by_article = {r["article_id"]: r for r in topic_rows}
    stakeholder = pick_one(class_rows, lambda r: r["classifier"] == BASELINE_CLASSIFIER)

    corpus = [a for a in articles if sentiment.get(a["id"], {}).get("sentiment") in SENTIMENTS]
    label_of = {a["id"]: sentiment[a["id"]]["sentiment"] for a in corpus}

    counts = _zero_counts()
    for label in label_of.values():
        counts[label] += 1
    total = len(corpus)
    distribution = {s: (counts[s] / total if total else 0) for s in SENTIMENTS}

    def stakeholder_of(article_id: int) -> str:
        return (stakeholder.get(article_id) or {}).get("stakeholder_category") or UNDETERMINED

    def topic_label_of(article: Row) -> Optional[str]:
        row = topic_by_article.get(article["id"])
        return (row.get("topic") or row["stable_topic_id"]) if row and row.get("stable_topic_id") else None

    dated = [(a["published_date"][:7], label_of[a["id"]]) for a in corpus if a.get("published_date")]
    topical = [(topic_label_of(a), label_of[a["id"]]) for a in corpus if topic_label_of(a)]
    stakeholders = [(stakeholder_of(a["id"]), label_of[a["id"]]) for a in corpus]

    newest_first = sorted(corpus, key=lambda a: a.get("published_date") or "", reverse=True)
    table = [
        {"id": a["id"], "title": a["title"], "source": a["source"], "url": a.get("url"),
         "published_date": a.get("published_date"), "stakeholder": stakeholder_of(a["id"]),
         "sentiment": label_of[a["id"]]}
        for a in newest_first[:max_articles]
    ]

    return {
        "analysed": total,
        "sentiment_distribution": distribution,
        "top_topics": top_topics(topic_rows),
        "sentiment_over_time": _breakdown(dated, sort_by_label=True),
        "sentiment_by_topic": _breakdown(topical),
        "sentiment_by_stakeholder": _breakdown(stakeholders),
        "articles": table,
        "error": None,
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/aggregation backend/tests/test_aggregation.py
git commit -m "Count the dashboard figures from analysis rows"
```

---

### Task 2: Reading the tables

**Files:**
- Create: `backend/agents/aggregation/results.py`
- Test: `backend/tests/test_aggregation.py` (append)

**Interfaces:**
- Consumes: a supabase client (`client.table(t).select(cols).eq(c, v).order("id").range(a, b).execute().data`).
- Produces:
  - `read_all(client, table: str, columns: str, page_size: int = 1000, **equals) -> list[dict]`
  - `read_corpus(client) -> tuple[list, list, list, list]`: `(articles, sentiment_rows, topic_rows, class_rows)`, ready for `build_results`.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_aggregation.py (put the two imports with the others at the top)
# PostgREST returns at most 1000 rows a request; a reader that trusts one request drops the rest.
from types import SimpleNamespace

from agents.aggregation.results import read_all, read_corpus


class FakeClient:
    """Tables behind PostgREST, which returns at most `cap` rows a request."""

    def __init__(self, tables, cap=1000):
        self.tables, self.cap = tables, cap
        self.requests = []

    def table(self, name):
        self.name, self.filters = name, []
        return self

    def select(self, columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, column):
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def execute(self):
        rows = [r for r in self.tables.get(self.name, []) if all(r.get(c) == v for c, v in self.filters)]
        start, end = self.window
        self.requests.append(self.name)
        return SimpleNamespace(data=rows[start:min(end + 1, start + self.cap)])


def test_read_all_gets_every_row_when_the_server_caps_a_request():
    rows = [{"id": i} for i in range(2500)]
    assert len(read_all(FakeClient({"articles": rows}, cap=1000), "articles", "id")) == 2500


def test_read_all_keeps_going_when_the_server_cap_is_below_the_page_size():
    rows = [{"id": i} for i in range(250)]
    assert len(read_all(FakeClient({"articles": rows}, cap=100), "articles", "id", page_size=1000)) == 250


def test_read_all_applies_equality_filters():
    rows = [{"id": 1, "ok": True}, {"id": 2, "ok": False}]
    assert read_all(FakeClient({"t": rows}), "t", "id", ok=True) == [{"id": 1, "ok": True}]


def test_read_corpus_reads_only_analysable_articles():
    client = FakeClient({
        "articles": [
            {"id": 1, "llm_relevant": True, "processing_status": "success"},
            {"id": 2, "llm_relevant": False, "processing_status": "success"},
            {"id": 3, "llm_relevant": True, "processing_status": "failed"},
        ],
        "sentiment_results": [{"id": 1, "article_id": 1}],
    })
    articles, sentiment, topics, classes = read_corpus(client)
    assert [a["id"] for a in articles] == [1]
    assert len(sentiment) == 1 and topics == [] and classes == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: `ImportError: cannot import name 'read_all'`.

- [ ] **Step 3: Implement**

```python
# backend/agents/aggregation/results.py  (created here, extended in Task 3)
"""
The dashboard payload, computed from the analysis tables.

PostgREST returns at most its max-rows per request whatever range is
asked for, so every read pages until a page comes back empty rather than
trusting a short page to be the last.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

Row = Dict[str, Any]


def read_all(client: Any, table: str, columns: str, page_size: int = 1000, **equals: Any) -> List[Row]:
    rows: List[Row] = []
    while True:
        query = client.table(table).select(columns)
        for column, value in equals.items():
            query = query.eq(column, value)
        page = query.order("id").range(len(rows), len(rows) + page_size - 1).execute().data
        if not page:
            return rows
        rows.extend(page)


def read_corpus(client: Any) -> Tuple[List[Row], List[Row], List[Row], List[Row]]:
    """(articles, sentiment, topic, classification) rows, ready for build_results."""
    articles = read_all(client, "articles", "id, title, source, published_date, url",
                        llm_relevant=True, processing_status="success")
    sentiment = read_all(client, "sentiment_results", "id, article_id, sentiment, method")
    topics = read_all(client, "topic_results", "id, article_id, stable_topic_id, topic")
    classes = read_all(client, "classification_results", "id, article_id, classifier, stakeholder_category")
    return articles, sentiment, topics, classes
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: 14 passed (10 from Task 1, 4 new).

- [ ] **Step 5: Commit**

```bash
git add backend/agents/aggregation/results.py backend/tests/test_aggregation.py
git commit -m "Read the analysis tables in full, past the row cap"
```

---

### Task 3: Serve it from /results

**Files:**
- Modify: `backend/agents/aggregation/results.py` (add to it), `backend/app.py` (`create_app`, `get_results`), `backend/orchestrator/topic_counts.py` (delete the reader), `backend/tests/helpers.py:14-22`, `backend/tests/test_topic_counts.py`
- Test: `backend/tests/test_aggregation.py` (append), `backend/tests/test_routes.py`

**Interfaces:**
- Consumes: `read_corpus`, `build_results`, `empty_results`; `agents.supabase_client.get_client`, `is_configured`.
- Produces:
  - `compute_results(client) -> dict`: raises on a read error.
  - `reader(client) -> Callable[[], dict]`: never raises; a failed read returns `empty_results(reason)`.
  - `reader_from_env() -> Callable[[], dict]`: `empty_results("Supabase is not configured...")` when it is not.
  - `create_app(runner=None, read_results=None)`; `build_client(registry=None, read_results=None)` in the test helper.

- [ ] **Step 1: Write the failing tests** (append to `test_aggregation.py`)

```python
# add compute_results and reader to the results import at the top
def test_reader_turns_a_failed_read_into_an_empty_payload_with_the_reason(caplog):
    class Broken:
        def table(self, name):
            raise RuntimeError("connection refused")

    result = reader(Broken())()
    assert result["analysed"] == 0 and "Could not read" in result["error"]
    assert "connection refused" in caplog.text


def test_compute_results_raises_so_the_pipeline_stage_can_fail():
    class Broken:
        def table(self, name):
            raise RuntimeError("connection refused")

    try:
        compute_results(Broken())
    except RuntimeError:
        return
    raise AssertionError("expected the read error to propagate")
```

Add to `test_routes.py`:

```python
def test_results_serves_the_reader_payload_unchanged():
    from agents.aggregation.compute import empty_results
    client, _ = build_client(read_results=lambda: empty_results("no data"))
    body = client.get("/api/v1/results").get_json()
    assert body["analysed"] == 0 and body["error"] == "no data"
    assert {"sentiment_distribution", "top_topics", "articles"} <= body.keys()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests -q`
Expected: failures on the new tests (`results` module missing, `read_results` not a `create_app` argument).

- [ ] **Step 3: Implement**

```python
# add to backend/agents/aggregation/results.py
# imports at the top: `import logging`, `from typing import Callable`,
# `from .compute import build_results, empty_results`, and `logger = logging.getLogger(__name__)`

def compute_results(client: Any) -> Dict[str, Any]:
    """Raises on a read error: the pipeline stage uses this, and a stage that cannot read its tables must fail."""
    # ponytail: recomputed per request (about 1.6 s, eight round trips). Threads, then a 60 s cache, then a snapshot row.
    return build_results(*read_corpus(client))


def reader(client: Any) -> Callable[[], Dict[str, Any]]:
    """For the endpoint: a failed read leaves the rest of the dashboard loading, with the reason."""
    def read() -> Dict[str, Any]:
        try:
            return compute_results(client)
        except Exception:
            logger.exception("Could not compute the dashboard results")
            return empty_results("Could not read the analysis tables; see the backend log.")

    return read


def reader_from_env() -> Callable[[], Dict[str, Any]]:
    from agents.supabase_client import get_client, is_configured

    if not is_configured():
        return lambda: empty_results("Supabase is not configured, so there are no results to read.")
    return reader(get_client())
```

In `backend/app.py`: replace the `read_topics` parameter, its default (`reader_from_env()` from `topic_counts`) and the hardcoded dict in `get_results()` with:

```python
from agents.aggregation.results import reader_from_env
...
def create_app(runner=None, read_results=None):
    ...
    if read_results is None:
        read_results = reader_from_env()
...
    @app.get("/api/v1/results")
    def get_results():
        """The dashboard payload, recomputed from the analysis tables on each request."""
        return jsonify(read_results())
```

Update the module docstring and the `get_results` TODO list accordingly (filters and auth stay as TODOs). In `tests/helpers.py` rename the `read_topics` parameter to `read_results`. In `orchestrator/topic_counts.py` delete `read_topic_rows`, `reader`, `reader_from_env` and the imports only they used; in `tests/test_topic_counts.py` delete the tests for those three (the `FakeClient` and the `/results` route test go with them; `top_topics` tests stay).

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests -q && cd .. && python -m pyright backend/`
Expected: all pass, pyright 0 errors (the suite is the prior total, minus the deleted reader tests, plus the new ones).

- [ ] **Step 5: Check it against the real database**

Run (read-only):
```bash
cd backend && source venv/bin/activate && python - <<'EOF'
from agents.aggregation.results import compute_results
from agents.supabase_client import get_client
r = compute_results(get_client())
print(r["analysed"], r["sentiment_distribution"], len(r["sentiment_over_time"]), len(r["sentiment_by_topic"]), r["sentiment_by_stakeholder"][:2])
EOF
```
Expected: `analysed` equal to the `sentiment_results` row count (323 today), 31 months, 5 topics, stakeholders led by `students` 131 and `educators` 115, taking about 1.6 s.

- [ ] **Step 6: Commit**

```bash
git add -A backend && git commit -m "Serve /results from the analysis tables"
```

---

### Task 4: The pipeline stage

**Files:**
- Modify: `backend/agents/adapters.py` (new class, docstring table), `backend/orchestrator/registry.py` (register), `backend/tests/test_registry_wiring.py`
- Test: `backend/tests/test_agent_adapters.py` (append)

**Interfaces:**
- Consumes: `compute_results(client)`, `RunContext.approved_ids`.
- Produces: `AggregationAgent(Agent)` with `name = "aggregation"` and `run(ctx) -> {"aggregated": int}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_agent_adapters.py
def test_aggregation_reports_the_corpus_size(monkeypatch):
    from agents.adapters import AggregationAgent
    monkeypatch.setattr("agents.adapters.get_client", lambda: object())
    monkeypatch.setattr("agents.aggregation.results.compute_results", lambda client: {"analysed": 323})
    ctx = RunContext(run_id=1, article_ids=[1, 2], approved_ids=[1, 2])
    assert AggregationAgent().run(ctx) == {"aggregated": 323}


def test_aggregation_raises_when_the_tables_cannot_be_read(monkeypatch):
    from agents.adapters import AggregationAgent

    def boom(client):
        raise RuntimeError("table missing")

    monkeypatch.setattr("agents.adapters.get_client", lambda: object())
    monkeypatch.setattr("agents.aggregation.results.compute_results", boom)
    with pytest.raises(RuntimeError):
        AggregationAgent().run(RunContext(run_id=1, article_ids=[], approved_ids=[]))
```

In `test_registry_wiring.py`: `REAL_STAGES = (COLLECTION, SECURITY, CLASSIFICATION, AGGREGATION)`, `STILL_STUBBED = (STANCE,)`.

- [ ] **Step 2: Run to verify they fail** (`ImportError: AggregationAgent`; registry still stubs aggregation).

- [ ] **Step 3: Implement**

```python
# backend/agents/adapters.py  (after TopicAgent)
class AggregationAgent(Agent):
    """
    Computes the dashboard figures for the whole corpus and reports the
    count. Nothing is stored: /results recomputes on request, so this
    stage is the run's check that the analysis tables can be read and
    aggregated, and it fails the stage if they cannot.
    """

    name = "aggregation"

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        from .aggregation import results

        payload = results.compute_results(get_client())
        return {"aggregated": payload["analysed"]}
```

In `registry.py`, import `AggregationAgent` in the `if live:` block's import line, and change the existing registration to `registry.register(AGGREGATION, AggregationAgent() if live else agents.stub_aggregation())`. Update the `adapters.py` docstring row to `aggregation   real - AggregationAgent`.

- [ ] **Step 4: Run** `cd backend && python -m pytest tests -q && cd .. && python -m pyright backend/`. Expected: all pass.

- [ ] **Step 5: Commit** `git commit -am "Run the aggregation stage against the real tables"`

---

### Task 5: Dashboard and docs

**Files:**
- Modify: `frontend/src/components/DashboardShell.jsx`, `README.md`, `NEXT_STEPS.md`, `docs/pipeline-coordinator.md`

- [ ] **Step 1:** In `DashboardShell.jsx` delete the two `PlaceholderNote` blocks (sentiment and articles) and update the header comment. When `results.analysed === 0`, show `results.error || "No sentiment results yet."` in a `PlaceholderNote` in place of the donut, so an empty database does not draw a flat chart.
- [ ] **Step 2:** Docs: aggregation is real; `/results` is recomputed per request; the old "aggregation: planned" rows change. `NEXT_STEPS.md` section 3 becomes "done, check it on a real run", pointing at this plan for the deferred items.
- [ ] **Step 3: Verify** `cd frontend && npm run build` (expected: builds), then run `python run_pipeline.py --live --backlog --limit 5` from `backend/` and confirm aggregation `succeeded` with `aggregated` equal to the corpus size, then `python app.py` plus `npm run dev` and read the page.
- [ ] **Step 4: Commit** `git commit -am "Show real results on the dashboard"`

---

## Not in this plan, and when to add it

- **The new charts** (timeline, topic by sentiment heatmap, stakeholder bars). The payload carries the data; drawing it is its own plan, so this one can be reviewed and merged first.
- **A snapshot table**, when `/results` takes over about a second or filters need per-filter numbers.
- **Filters** (date range, source, topic): `build_results` takes plain row lists, so filtering rows before the call is the extension point.
- **Stance**: the table is empty and no code exists.

## Self-review

- Spec coverage: payload contract kept (Task 1, 3), real stage (Task 4), the three breakdowns (Task 1), docs and placeholder notes (Task 5). Review Focus items 1-5 each map to a named test.
- Placeholder scan: none; every code step has code.
- Type consistency: `pick_one`, `build_results`, `empty_results`, `read_all`, `read_corpus`, `compute_results`, `reader`, `reader_from_env`, `AggregationAgent` are named identically in every task that uses them. `build_results` takes `(articles, sentiment_rows, topic_rows, class_rows)` and `read_corpus` returns exactly that order.
