# Aggregation MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /api/v1/results` serves sentiment figures computed from the real analysis tables instead of the hardcoded placeholder, including the three breakdowns the demo reviewers asked for: sentiment over time, by topic, and by stakeholder. The filter panel narrows them like it already narrows topics and articles.

**Amended 2026-10-13, after the dashboard MVP (PR #24) merged.** The first version of this plan replaced `/results` with a new, unfiltered reader. Since then `/results` is served from `orchestrator/corpus.py`: one merged row per analysable article (classification and topic already picked), filtered per request, behind a 60-second cache. Ravi chose to build on that ("Adapt to corpus"). What changed:

- The corpus reader also reads `sentiment_results` and gives each article one `sentiment` (Task 2). No second reader, no second paging helper: `corpus.page_all` already pages past the 1,000-row cap.
- The counting rules are one pure function over corpus articles, `sentiment_figures` (Task 1). Topic counts and the article list stay where the dashboard MVP put them.
- `/results` adds the figures for the filtered articles (Task 3). `topic_counts.py`'s reader was already deleted by the dashboard MVP.
- The e2e checks that assert the placeholder (D1) and the stub list (P2) change with it (Task 5).

**Architecture:** `orchestrator/corpus.py` reads `articles`, `classification_results`, `topic_results` and now `sentiment_results`, and merges them to one row per article. `agents/aggregation/compute.py` turns those rows into the sentiment figures. `app.py` serves them for the filtered articles next to the corpus payload. The pipeline's aggregation stage runs the same reader and computation once per run, so a broken table fails the stage loudly instead of only breaking the page. No new table, no migration, no snapshot.

**Tech Stack:** Python 3.13, Flask 3.0, supabase-py (PostgREST), pytest, pyright, React 18 (Vite) with Recharts, Playwright for the e2e checks. No new dependencies.

**Spec:** [`docs/pipeline-coordinator.md`](../../pipeline-coordinator.md) (the agent contract, "For agent owners: plugging in your agent") and the `/results` payload in [`backend/app.py`](../../../backend/app.py) and [`backend/orchestrator/corpus.py`](../../../backend/orchestrator/corpus.py). Supersedes [`2026-09-29-aggregation-agent.md`](2026-09-29-aggregation-agent.md). There is no standalone written spec; the decisions below were approved by Ravi (PR #21, and the corpus amendment on 2026-10-13).

## Global Constraints

- **`orchestrator/` never imports an agent.** `agents/adapters.py` is the one file that knows both sides. `agents/aggregation/` may import from `orchestrator/`, never the reverse.
- **Agents raise on failure and never retry internally.** Retry counts live in `orchestrator/retry.py`; aggregation's policy is untouched.
- **The pipeline stage reads through `agents/supabase_client.get_client()`.** Never build another client, never call `load_dotenv()` at import time.
- **The test suite never touches the network.** It passes `live=False` and behaves the same with or without `backend/.env`.
- **`python -m pyright backend/` adds no errors** (run from the repo root; 7 errors and 2 warnings today, none in files this plan touches). `agents/aggregation` is not added to `exclude`.
- **No invented numbers.** Anything that cannot be computed is reported as missing, with a reason, never as a zero that reads like a finding.
- **Payload contract is additive.** `sentiment_distribution` keeps its name and shape (shares 0–1 for `positive`, `neutral`, `negative`) so the donut keeps working; `top_topics`, `articles` and `filter_options` are untouched.

## Review Focus

Most likely to bite first. Each line's test is added to the task named.

1. **PostgREST caps a request at 1000 rows.** A reader that trusts one request aggregates a subset and publishes it as the whole picture, with no error. → sentiment paging test, **Task 2**.
2. **Two sentiment methods per article** once VADER runs as a fallback. Both rows must not count, and RoBERTa's wins whatever the row order. → **Task 2**.
3. **An article with sentiment but no topic or stakeholder yet.** It belongs in the totals and the timeline, is left out of the by-topic breakdown, and shows as `undetermined` by stakeholder. It must not raise. → **Task 1**.
4. **Empty or unreadable data, or filters that match nothing** must give a valid payload with `analysed: 0` and a reason, not a `ZeroDivisionError` or a 500, from the endpoint. The pipeline stage must still raise on a read error. → **Tasks 1, 3, 4**.
5. **A sentiment label the rules don't know** (a future `mixed`) must not be counted as one of the three, or crash a `counts[label] += 1`. → **Task 1**.

## Design decisions this plan makes

1. **Recompute on request, no snapshot table.** The figures are computed from the cached corpus (60 s), so they cost no extra reads. A snapshot needs a manual migration and could not follow the filters. Upgrade path: a snapshot row per run, when runs need comparing over time.
2. **The sentiment figures cover the filtered articles that have a sentiment result.** Articles without one stay in the article list and the topic counts, but not in the shares: counting them would deflate every share.
3. **Aggregation reads the whole corpus, not `ctx.approved_ids`.** The dashboard shows the state of the corpus; a run that collected 40 articles must not replace a 323-article picture with a 40-article one.
4. **Preference order when an article has several sentiment rows:** `roberta_news` over any other method; among equals, the newest row. (Stakeholder and topic: as the corpus already does.)
5. **Months, not weeks.** Dates run 2022-11 to 2026-10; weekly buckets would be mostly empty.
6. **`stance_results` is not read.** The table is empty and nothing on the dashboard uses it.

---

## File Structure

**New**
- `backend/agents/aggregation/__init__.py`: empty package marker.
- `backend/agents/aggregation/compute.py`: `sentiment_figures`, pure: no database, no clock.
- `backend/tests/test_aggregation.py`: the counting rules' tests.

**Modified**
- `backend/orchestrator/corpus.py`: read `sentiment_results`, one `sentiment` per article.
- `backend/app.py`: serve the figures; delete `PLACEHOLDER_SENTIMENT`.
- `backend/agents/adapters.py`: `AggregationAgent`. `backend/orchestrator/registry.py`: register it where live.
- Tests: `test_corpus.py`, `test_dashboard_routes.py`, `test_agent_adapters.py`, `test_registry_wiring.py`.
- `frontend/src/components/DashboardShell.jsx` (real donut, reason when empty), `AdminConsole.jsx` (aggregation is no longer a stub).
- `backend/e2e/`: R1 and D1 check sentiment against the raw tables; P2's stub note comes from the registry.
- `README.md`, `NEXT_STEPS.md`, `docs/pipeline-coordinator.md`: stage is real now.

---

### Task 1: The counting rules

**Files:**
- Create: `backend/agents/aggregation/__init__.py`, `backend/agents/aggregation/compute.py`
- Test: `backend/tests/test_aggregation.py`

**Interfaces:**
- Consumes: corpus articles: dicts with `published_date` (ISO string or None), `stakeholder` (str or None), `topic` (label or None when unassigned), `sentiment` (str or None).
- Produces: `sentiment_figures(articles: Iterable[dict], reason_if_empty: str = NO_SENTIMENT) -> dict` with keys `analysed`, `sentiment_distribution`, `sentiment_over_time`, `sentiment_by_topic`, `sentiment_by_stakeholder`, `sentiment_reason`. Breakdown rows: `{"label", "positive", "neutral", "negative", "total"}`. Constants `SENTIMENTS`, `UNDETERMINED`, `NO_SENTIMENT`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_aggregation.py
"""
The aggregation rules. What goes quietly wrong here: an article without a
sentiment deflating every share, a missing topic raising instead of being
skipped, an unknown label crashing the count, an empty corpus dividing by
zero.
"""
from agents.aggregation.compute import NO_SENTIMENT, sentiment_figures


def art(id, sentiment="neutral", month="2025-03", topic=None, stakeholder="educators"):
    return {"id": id, "published_date": f"{month}-10T10:00:00+00:00" if month else None,
            "topic": topic, "stakeholder": stakeholder, "sentiment": sentiment}


def test_distribution_is_shares_of_the_analysed_articles():
    arts = [art(1, "positive"), art(2, "neutral"), art(3, "neutral"), art(4, "negative")]
    result = sentiment_figures(arts)
    assert result["sentiment_distribution"] == {"positive": 0.25, "neutral": 0.5, "negative": 0.25}
    assert result["analysed"] == 4 and result["sentiment_reason"] is None


def test_articles_without_a_known_sentiment_are_left_out():
    result = sentiment_figures([art(1, "positive"), art(2, None), art(3, "mixed")])
    assert result["analysed"] == 1
    assert result["sentiment_distribution"] == {"positive": 1.0, "neutral": 0, "negative": 0}


def test_timeline_buckets_by_month_oldest_first_and_skips_undated():
    arts = [art(1, "positive", "2025-03"), art(2, "negative", "2024-11"), art(3, "neutral", None)]
    result = sentiment_figures(arts)
    assert [(m["label"], m["total"]) for m in result["sentiment_over_time"]] == [("2024-11", 1), ("2025-03", 1)]
    assert result["analysed"] == 3  # the undated article still counts in the totals


def test_by_topic_counts_each_topic_and_leaves_out_unassigned_articles():
    arts = [art(1, "positive", topic="Adoption"), art(2, "negative", topic="Adoption"), art(3, "neutral")]
    assert sentiment_figures(arts)["sentiment_by_topic"] == [
        {"label": "Adoption", "positive": 1, "neutral": 0, "negative": 1, "total": 2}]


def test_breakdowns_are_largest_first_then_by_label():
    arts = [art(1, stakeholder="students"), art(2, stakeholder="educators"), art(3, stakeholder="students")]
    assert [r["label"] for r in sentiment_figures(arts)["sentiment_by_stakeholder"]] == ["students", "educators"]


def test_an_article_without_a_stakeholder_is_undetermined():
    by = {r["label"]: r for r in sentiment_figures([art(1, "negative", stakeholder=None)])["sentiment_by_stakeholder"]}
    assert by["undetermined"]["negative"] == 1


def test_no_analysed_articles_gives_zeros_and_the_reason_not_an_error():
    result = sentiment_figures([art(1, None)], reason_if_empty="No articles match these filters.")
    assert result["analysed"] == 0
    assert result["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 0}
    assert result["sentiment_over_time"] == result["sentiment_by_topic"] == result["sentiment_by_stakeholder"] == []
    assert result["sentiment_reason"] == "No articles match these filters."
    assert sentiment_figures([])["sentiment_reason"] == NO_SENTIMENT
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'agents.aggregation'`.

- [ ] **Step 3: Implement**

```python
# backend/agents/aggregation/__init__.py  (empty)
```

```python
# backend/agents/aggregation/compute.py
"""
The aggregation rules, as pure functions.

No database, no network, no clock: corpus articles in (one merged row per
article, see orchestrator/corpus.py), dashboard figures out, so every
counting decision can be tested without a fake Supabase.

Only articles with a known sentiment count. Articles without one are
still in the article list and the topic counts; counting them here would
deflate every share.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

SENTIMENTS = ("positive", "neutral", "negative")
UNDETERMINED = "undetermined"
NO_SENTIMENT = "No sentiment results yet."

Row = Dict[str, Any]


def _zero_counts() -> Dict[str, int]:
    return {s: 0 for s in SENTIMENTS}


def _breakdown(pairs: Iterable[Tuple[str, str]], by_label: bool = False) -> List[Row]:
    """(label, sentiment) pairs -> one row per label with a count per sentiment, largest first."""
    rows: Dict[str, Row] = {}
    for label, sentiment in pairs:
        row = rows.setdefault(label, {"label": label, **_zero_counts(), "total": 0})
        row[sentiment] += 1
        row["total"] += 1
    if by_label:
        return sorted(rows.values(), key=lambda r: r["label"])
    return sorted(rows.values(), key=lambda r: (-r["total"], r["label"]))


def sentiment_figures(articles: Iterable[Row], reason_if_empty: str = NO_SENTIMENT) -> Row:
    """The sentiment share, and its breakdowns by month, topic and stakeholder."""
    analysed = [a for a in articles if a.get("sentiment") in SENTIMENTS]
    counts = _zero_counts()
    for a in analysed:
        counts[a["sentiment"]] += 1
    total = len(analysed)
    reason: Optional[str] = None if total else reason_if_empty
    return {
        "analysed": total,
        "sentiment_distribution": {s: (counts[s] / total if total else 0) for s in SENTIMENTS},
        "sentiment_over_time": _breakdown(((a["published_date"][:7], a["sentiment"])
                                           for a in analysed if a.get("published_date")), by_label=True),
        "sentiment_by_topic": _breakdown((a["topic"], a["sentiment"]) for a in analysed if a.get("topic")),
        "sentiment_by_stakeholder": _breakdown((a.get("stakeholder") or UNDETERMINED, a["sentiment"])
                                               for a in analysed),
        "sentiment_reason": reason,
    }
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_aggregation.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agents/aggregation backend/tests/test_aggregation.py
git commit -m "Count the dashboard's sentiment figures from corpus articles"
```

---

### Task 2: Sentiment in the corpus

**Files:**
- Modify: `backend/orchestrator/corpus.py` (`read_corpus`, module docstring)
- Test: `backend/tests/test_corpus.py` (append to the `read_corpus` section)

**Interfaces:**
- Consumes: the `sentiment_results` table, columns `id, article_id, sentiment, method`.
- Produces: every article from `corpus.read_corpus(client)` carries `sentiment` (str, or None without a result). Constant `PREFERRED_SENTIMENT_METHOD = "roberta_news"`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_corpus.py, after test_the_newest_topic_row_wins_and_no_stable_id_means_unassigned
def sentiment(article_id, label, method="roberta_news", id=None):
    return {"id": id or article_id, "article_id": article_id, "sentiment": label, "method": method}


def test_roberta_beats_vader_whatever_the_row_order_and_no_row_means_none():
    client = FakeSupabase(
        articles=[article(1), article(2), article(3)],
        sentiment_results=[
            sentiment(1, "positive", id=1), sentiment(1, "negative", "vader", id=9),
            sentiment(2, "neutral", "vader", id=2), sentiment(2, "negative", "vader", id=8),
        ],
    )
    by_id = {a["id"]: a["sentiment"] for a in corpus.read_corpus(client)}
    assert by_id == {1: "positive", 2: "negative", 3: None}


def test_every_sentiment_page_is_read_even_when_the_server_caps_pages():
    client = FakeSupabase(cap=2, articles=[article(i) for i in range(1, 6)],
                          sentiment_results=[sentiment(i, "neutral") for i in range(1, 6)])
    assert [a["sentiment"] for a in corpus.read_corpus(client)] == ["neutral"] * 5
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_corpus.py -q`
Expected: the two new tests fail with `KeyError: 'sentiment'`.

- [ ] **Step 3: Implement**

In `read_corpus`, after the `topic_rows` read:

```python
    sentiment_rows = page_all(lambda: client.table("sentiment_results")
                              .select("id, article_id, sentiment, method").order("id"))
```

after `newest_topic = ...`:

```python
    # Ordered by id, so a later row of the same preference replaces an earlier one.
    sentiment: Dict[Any, Mapping[str, Any]] = {}
    for row in sentiment_rows:
        current = sentiment.get(row["article_id"])
        if current is None or _method_rank(row) >= _method_rank(current):
            sentiment[row["article_id"]] = row
```

in the per-article dict: `"sentiment": sentiment.get(article["id"], {}).get("sentiment"),`

next to `_classifier_rank`:

```python
def _method_rank(row: Mapping[str, Any]) -> int:
    return 1 if row.get("method") == PREFERRED_SENTIMENT_METHOD else 0
```

and `PREFERRED_SENTIMENT_METHOD = "roberta_news"` next to `BASELINE_CLASSIFIER`. In the module docstring: "reads four tables (articles, classification_results, topic_results, sentiment_results)", and a merge rule: "sentiment: `roberta_news` beats any other method; ties go to the newest row. No row means no sentiment (None)."

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_corpus.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/corpus.py backend/tests/test_corpus.py
git commit -m "Give each corpus article one sentiment, RoBERTa's first"
```

---

### Task 3: Serve the figures from /results

**Files:**
- Modify: `backend/app.py` (`get_results`, module docstring; delete `PLACEHOLDER_SENTIMENT`)
- Test: `backend/tests/test_dashboard_routes.py`

**Interfaces:**
- Consumes: `sentiment_figures` (Task 1); corpus articles with `sentiment` (Task 2); `corpus.filter_articles`, `corpus.results_payload`.
- Produces: `/api/v1/results` = the corpus payload plus every key of `sentiment_figures`, computed over the filtered articles.

- [ ] **Step 1: Write the failing tests**

In `test_dashboard_routes.py`: give the two `ARTICLES` a sentiment (`"sentiment": "positive"` on 1, `"sentiment": "negative"` on 2). In `test_results_without_filters_lists_the_whole_corpus` replace the placeholder assertion with:

```python
    assert body["sentiment_distribution"] == {"positive": 0.5, "neutral": 0, "negative": 0.5}
    assert body["analysed"] == 2 and body["sentiment_reason"] is None
```

append to `test_results_applies_the_filters_to_articles_and_topics`:

```python
    assert body["sentiment_distribution"] == {"positive": 0, "neutral": 0, "negative": 1.0}
    assert [r["label"] for r in body["sentiment_by_stakeholder"]] == ["students"]
```

append to `test_results_without_a_database_still_loads_and_says_why`:

```python
    assert body["analysed"] == 0 and body["sentiment_reason"] == "Database down."
```

and add:

```python
def test_filters_that_match_nothing_give_empty_figures_with_the_reason():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results?stakeholder=parents").get_json()
    assert body["analysed"] == 0
    assert body["sentiment_reason"] == "No analysed articles match these filters."
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_dashboard_routes.py -q`
Expected: the four tests fail (placeholder shares served; no `analysed` key).

- [ ] **Step 3: Implement**

In `app.py`: delete `PLACEHOLDER_SENTIMENT` and its comment; import `from agents.aggregation.compute import NO_SENTIMENT, sentiment_figures`; and in `get_results`, after the filters:

```python
        current = read_corpus()
        if not current["available"]:
            reason = current["reason"]
        elif any(filters.values()):
            reason = "No analysed articles match these filters."
        else:
            reason = NO_SENTIMENT
        matched = corpus.filter_articles(current["articles"], filters)
        return jsonify({
            **corpus.results_payload(current, filters),
            **sentiment_figures(matched, reason),
        })
```

Update the module docstring (`/results` line: sentiment figures are computed from `sentiment_results`) and the `get_results` docstring (drop "sentiment_distribution is still a placeholder").

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest -q && cd .. && python -m pyright backend/`
Expected: all pass; pyright reports no new errors.

- [ ] **Step 5: Check it against the real database** (read-only)

```bash
cd backend && python - <<'EOF'
from orchestrator import corpus
from agents.supabase_client import get_client
from agents.aggregation.compute import sentiment_figures
r = sentiment_figures(corpus.read_corpus(get_client()))
print(r["analysed"], r["sentiment_distribution"], len(r["sentiment_over_time"]), len(r["sentiment_by_topic"]), r["sentiment_by_stakeholder"][:2])
EOF
```
Expected: `analysed` equal to the analysable articles that have a `sentiment_results` row (323 on 2026-10-13), about 72% neutral, 15% negative, 12% positive, 5 topics.

- [ ] **Step 6: Commit**

```bash
git add backend/app.py backend/tests/test_dashboard_routes.py
git commit -m "Serve real sentiment figures from /results, filtered"
```

---

### Task 4: The pipeline stage

**Files:**
- Modify: `backend/agents/adapters.py` (new class, docstring table), `backend/orchestrator/registry.py` (register), `backend/tests/test_registry_wiring.py`
- Test: `backend/tests/test_agent_adapters.py` (append)

**Interfaces:**
- Consumes: `corpus.read_corpus(client)` (raises on a read error), `sentiment_figures`.
- Produces: `AggregationAgent(Agent)` with `name = "aggregation"` and `run(ctx) -> {"aggregated": int}` (the analysed count over the whole corpus).

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_agent_adapters.py
def test_aggregation_reports_the_analysed_articles_in_the_whole_corpus(monkeypatch):
    from agents.adapters import AggregationAgent
    rows = [{"id": 1, "sentiment": "positive"}, {"id": 2, "sentiment": None}, {"id": 3, "sentiment": "neutral"}]
    monkeypatch.setattr("agents.adapters.get_client", lambda: object())
    monkeypatch.setattr("orchestrator.corpus.read_corpus", lambda client: rows)
    ctx = RunContext(run_id=1, article_ids=[1], approved_ids=[1])
    assert AggregationAgent().run(ctx) == {"aggregated": 2}


def test_aggregation_raises_when_the_tables_cannot_be_read(monkeypatch):
    from agents.adapters import AggregationAgent

    def boom(client):
        raise RuntimeError("table missing")

    monkeypatch.setattr("agents.adapters.get_client", lambda: object())
    monkeypatch.setattr("orchestrator.corpus.read_corpus", boom)
    with pytest.raises(RuntimeError, match="table missing"):
        AggregationAgent().run(RunContext(run_id=1, article_ids=[], approved_ids=[]))
```

In `test_registry_wiring.py`: `REAL_STAGES = (COLLECTION, SECURITY, CLASSIFICATION, AGGREGATION)`, `STILL_STUBBED = (STANCE,)`.

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_agent_adapters.py tests/test_registry_wiring.py -q`
Expected: `ImportError: cannot import name 'AggregationAgent'`, and the live wiring test fails on the aggregation stub.

- [ ] **Step 3: Implement**

```python
# backend/agents/adapters.py, after TopicAgent; `from orchestrator import corpus` with the other orchestrator imports
class AggregationAgent(Agent):
    """
    Computes the dashboard's sentiment figures over the whole corpus and
    reports how many articles they cover. Nothing is stored: /results
    recomputes them per request, so this stage is the run's check that
    the analysis tables can be read and aggregated. It fails if they can't.
    """

    name = "aggregation"

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        from .aggregation.compute import sentiment_figures

        figures = sentiment_figures(corpus.read_corpus(get_client()))
        return {"aggregated": figures["analysed"]}
```

In `registry.py`, add `AggregationAgent` to the `if live:` block's import line and register it there (`registry.register(AGGREGATION, AggregationAgent())`), with the stub in the `else` branch; drop the unconditional stub registration. Update the `adapters.py` docstring row to `aggregation     real - AggregationAgent (sentiment figures over the corpus)`.

- [ ] **Step 4: Run** `cd backend && python -m pytest -q && cd .. && python -m pyright backend/`. Expected: all pass; no new pyright errors.

- [ ] **Step 5: Commit** `git commit -am "Run the aggregation stage against the real tables"`

---

### Task 5: Dashboard, end-to-end checks and docs

**Files:**
- Modify: `frontend/src/components/DashboardShell.jsx`, `frontend/src/components/AdminConsole.jsx`
- Modify: `backend/e2e/database.py`, `backend/e2e/test_1_pipeline_api.py`, `backend/e2e/test_2_results_api.py`, `backend/e2e/test_3_dashboard.py`
- Modify: `README.md`, `NEXT_STEPS.md`, `docs/pipeline-coordinator.md`, `docs/testing/e2e-test-report.md`

- [ ] **Step 1: Dashboard.** In `DashboardShell.jsx` delete the sentiment `PlaceholderNote` (and the component, now unused) and update the header comment. In the sentiment card, when `results.analysed === 0` show `<p className="empty-note">{results.sentiment_reason}</p>` instead of the donut, so an empty database does not draw a flat chart; otherwise a `card-subtitle` "Share of the {analysed} matching article(s) with a sentiment result." above the donut. In `AdminConsole.jsx` drop `aggregation` from `STUBBED_STAGES` and update its comment.
- [ ] **Step 2: End-to-end checks (write them first).**
  - `database.sentiment_facet(client)`: from the raw tables, the analysable articles' sentiment (RoBERTa's row first, then the newest), as `{"analysed": n, "shares": {...}}`.
  - R1 also asserts `/results`' `analysed` and `sentiment_distribution` equal it.
  - D1 asserts the donut's labels read `Positive N%`, `Neutral N%`, `Negative N%` with those shares rounded as the page does (half up), and that the "Placeholder figures" note is gone.
  - P2's "stub stages" note lists the stages the registry actually stubbed, instead of a fixed list.
  - Run `python -m pytest e2e -k "r1 or d1"` before Step 1 is built into the frontend build: expected R1 passes only after Task 3, D1 fails on the placeholder note until Step 1. Then after Step 1: both pass.
- [ ] **Step 3: Docs.** Aggregation is real; `/results` sentiment is computed per request from the corpus. README: drop the "Sentiment donut is a hardcoded placeholder" MVP row, add an Aggregation row (shortcut: recomputed from the cached corpus per request, the stage stores nothing; ceiling: no history of figures per run; better: a snapshot row per run). `NEXT_STEPS.md` section 3 becomes "done, check it on a real run". Coordinator doc: aggregation row real. E2E report: a short note that the sentiment placeholder is gone and R1/D1 check sentiment.
- [ ] **Step 4: Verify.** `cd frontend && npm run build` (builds); the offline suite and pyright; then the e2e suite without `--collect` (two real runs over 5 stored articles, which also proves the aggregation stage succeeds in a real run: P2 and D3).
- [ ] **Step 5: Commit** `git commit -am "Show real sentiment on the dashboard"`

---

## Not in this plan, and when to add it

- **The new charts** (timeline, topic by sentiment, stakeholder bars). The payload carries the data; drawing it is its own plan.
- **A sentiment column in the article table.** The corpus now has it; add it with the charts.
- **A snapshot table**, when runs need comparing over time.
- **Stance**: the table is empty and no code exists.

## Self-review

- Spec coverage: payload contract kept (Tasks 1, 3), real stage (Task 4), the three breakdowns (Task 1), dashboard, e2e and docs (Task 5). Review Focus items 1–5 each map to a named test.
- Placeholder scan: none; every code step has code.
- Type consistency: `sentiment_figures`, `NO_SENTIMENT`, `PREFERRED_SENTIMENT_METHOD`, `AggregationAgent` are named identically in every task that uses them; corpus articles carry `sentiment` from Task 2 on, which Tasks 1, 3 and 4 consume.
