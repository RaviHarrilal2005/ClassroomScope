# Aggregation Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real aggregation agent so `GET /api/v1/results` serves
figures computed from the corpus instead of the hardcoded stub, and says
plainly which figures no agent produces yet.

**Architecture:** The agent reads the corpus and the analysis result
tables, computes the dashboard payload with pure functions, and writes it
as one JSONB snapshot row to a new `aggregate_results` table. The API
reads the newest snapshot back through a `ResultsStore` in
`orchestrator/`, mirroring how `RunStore` already works, so
`orchestrator/` still never imports an agent. Facets whose source table
has no rows — sentiment above all — come back `available: false` with a
reason rather than as zeros.

**Tech Stack:** Python 3.13, Flask 3.0, supabase-py (PostgREST), pytest,
pyright, React 18 (Vite). No new dependencies.

**Spec:** [`docs/pipeline-coordinator.md`](../../pipeline-coordinator.md) —
the agent contract ("For agent owners: plugging in your agent"), the
failure rules, and the open questions. The output contract is the payload
in [`backend/app.py`](../../../backend/app.py) `get_results()`, which its
own docstring describes as "shaped like what the real Aggregation Service
(design doc, Section 6.5) will eventually produce, so the front end can be
built against a stable contract".

**There is no standalone written spec for this agent.** The design doc
sections it refers to (2 and 6.5) are not in this repo. This plan
therefore makes five design decisions the spec does not settle. They are
listed under [Design decisions this plan makes](#design-decisions-this-plan-makes),
and Task 9 records each one in the docs as an open question, in the same
form as the six already there. A reviewer should read that list first:
rejecting one of them changes the plan, not just the code.

## Global Constraints

- **`orchestrator/` never imports an agent.** `agents/<stage>/` is its
  owner's code; `agents/adapters.py` is the only file that knows about
  both (`docs/pipeline-coordinator.md`, "Code layout"). The read side of
  the snapshot therefore lives in `orchestrator/results_store.py` and
  builds its own client with `create_client(url, key)` from
  `os.environ`, exactly as `SupabaseRunStore.from_env()` does.
- **Agents raise on failure.** No internal retries, no swallowed errors.
  Retry counts live in `orchestrator/retry.py`; aggregation is
  `RetryPolicy(max_attempts=2, backoff_base=1.0)` and is not changed by
  this plan.
- **Agents read and write through `agents/supabase_client.py`'s
  `get_client()`.** Never build another client, and never call
  `load_dotenv()` at import time — these modules are imported by the
  test suite and by the app, not only run as scripts.
- **The test suite never touches the network.** It passes `live=False`
  and must behave identically on a machine with and without
  `backend/.env`. The suite is **89 tests** before this plan; every task
  that adds tests states the new total.
- **`python -m pyright backend/` must stay clean**, run from the repo
  root. `backend/agents/aggregation` is **not** added to `exclude` in
  `pyrightconfig.json` — it pulls in no heavy dependencies.
- **`SUPABASE_URL` is the API endpoint** (`https://<ref>.supabase.co`),
  not the dashboard page, and `SUPABASE_KEY` must be the **secret**
  (`sb_secret_…`) key. The publishable key cannot write the pipeline
  tables (42501 permission denied).
- **Migrations cannot be applied with `supabase db push`** — the remote
  records twelve migrations with no files in this repo. Apply through the
  dashboard SQL editor, as `20260924000153_align_stage_name_constraint.sql`
  was. **Do not run `supabase migration repair --status reverted`**: it
  deletes rows from the remote history rather than undoing anything.
- **No invented numbers reach the dashboard.** A facet with no data is
  marked unavailable, with a reason. This is the point of the feature:
  the endpoint it replaces served percentages that read as findings.

## Review Focus

Five things the spec implies but no task's own happy-path tests would
exercise, most likely to bite a person using this software first. Each
line's test is added below to the task that owns the code.

1. **PostgREST returns at most 1000 rows per request**, whatever the
   query asks for. The corpus is 814 articles today. The first run after
   it crosses 1000 would aggregate a subset and publish it as the whole
   picture, with no error anywhere. → paging test in **Task 4**.
2. **`classification_results` holds one row per classifier per article**
   (upserted on `article_id,classifier`), so an article classified by
   both the keyword scorer and the LLM appears twice. Counting the table
   directly double-counts those stakeholders. → `best_classification`
   test in **Task 2**.
3. **`sentiment_results` may not be in the schema at all** — no sentiment
   agent exists on any branch — and PostgREST reports an absent table as
   an error, not as zero rows. Letting that raise would fail the
   aggregation stage on every run and leave every run at
   `completed_with_errors`. → `read_optional` test in **Task 4**, and a
   whole-agent test in **Task 5**.
4. **BERTopic labels its outlier cluster `-1_students_ai_school`**, and
   `topic_results.topic` is nullable. Those are articles it could not
   place, not a theme, and the outlier bucket is usually the largest — so
   it would top the chart. → `top_topics` test in **Task 2**.
5. **An empty or unanalysed corpus** — a fresh database, or one where
   every analysis stage failed — must produce a payload, not a
   `ZeroDivisionError` and not a 500. → empty-input tests in **Task 2**,
   and a no-snapshot endpoint test in **Task 7**.

## Design decisions this plan makes

1. **Aggregation reads the whole analysable corpus, not
   `ctx.approved_ids`.** Contract rule 8 says a stage stays inside the
   IDs it was given. Aggregation is the one stage where that would be
   wrong: the dashboard shows the state of the corpus, and a run that
   collected 40 new articles must not replace an 814-article picture
   with a 40-article one. The snapshot records `run_id` and
   `articles_in_run` so the two numbers stay tellable apart.
2. **"Analysable corpus" means `is_relevant = true` and
   `processing_status = 'success'`** — the same articles collection hands
   to analysis. An irrelevant article, or one whose page never
   downloaded, has no `clean_content` and so no analysis rows; counting
   it would deflate every percentage.
3. **One snapshot row per run, payload as JSONB, insert not upsert.** The
   snapshots are a history: the dashboard shows the newest, and a failed
   run's row stays visible. The cost is that a frozen snapshot cannot
   answer a filtered query, so `FilterPanel` will need either
   per-request aggregation or a normalised schema. Deliberate YAGNI — no
   filter UI exists.
4. **`aggregate_results.run_id` has no foreign key to `pipeline_runs`.**
   `run_pipeline.py` always keeps run status in memory, never in
   `pipeline_runs`, so a `--live` demo run's `ctx.run_id` names a run
   that was never recorded. A foreign key would make the demo fail at its
   last stage.
5. **Aggregation expects `sentiment_results(article_id, sentiment_label)`**
   with values in `positive` / `neutral` / `negative`. No sentiment agent
   exists, so this plan defines the column it will read and reports the
   facet unavailable — naming the column it looked for — until the
   sentiment owner writes it. `stance_results` is not read at all: the
   dashboard payload has no stance field.

---

## File Structure

**New — the agent (its owner's code; nothing in `orchestrator/` imports it):**

- `backend/agents/aggregation/__init__.py` — package marker, empty.
- `backend/agents/aggregation/compute.py` — the aggregation rules as pure
  functions. No Supabase, no network, no clock: the caller passes
  `generated_at` in. The counting decisions live here so they can be
  tested directly instead of through a fake database.
- `backend/agents/aggregation/db.py` — the Supabase layer: paged reads of
  the corpus and the analysis tables, tolerance for a table that is not
  in the schema, and the snapshot insert. Named to match
  `agents/collection/db.py`, which plays the same role for collection.

**New — the read side and the endpoint (orchestrator's half):**

- `backend/orchestrator/results_store.py` — `ResultsStore` interface,
  `EmptyResultsStore`, `SupabaseResultsStore`. Mirrors `store.py` /
  `supabase_store.py`.
- `backend/orchestrator/results_routes.py` — `create_results_blueprint`,
  serving `GET /api/v1/results`. Mirrors `routes.py`.

**New — schema:**

- `supabase/migrations/20260929120000_add_aggregate_results.sql`

**New — tests:**

- `backend/tests/fakes.py` — the fake Supabase client, moved out of
  `test_agent_adapters.py` so the aggregation tests share it.
- `backend/tests/test_aggregation_compute.py` — the pure rules.
- `backend/tests/test_aggregation_agent.py` — `db.py` and the adapter,
  against the fake client.
- `backend/tests/test_results_routes.py` — the store and the endpoint.

**Modified:**

- `backend/agents/adapters.py` — add `AggregationAgent`.
- `backend/orchestrator/registry.py` — register it in the `live` branch.
- `backend/app.py` — `build_results_store()`, register the blueprint,
  delete the stub `get_results()`.
- `backend/tests/conftest.py` — shared `fake_client` fixture.
- `backend/tests/test_agent_adapters.py` — import the fake from `fakes.py`.
- `backend/tests/test_registry_wiring.py` — aggregation leaves
  `STILL_STUBBED`.
- `backend/tests/test_schema_sync.py` — check `aggregate_results`.
- `docs/pipeline_tables.sql` — declare `aggregate_results`.
- `frontend/src/components/DashboardShell.jsx` — render real aggregates,
  name what is missing.
- `frontend/src/state/ViewStateContext.jsx` — refresh results when a run
  finishes.
- `frontend/src/api/apiClient.js` — correct the `getResults()` status note.
- `docs/pipeline-coordinator.md`, `README.md` — status, the new table,
  the new open questions.

---

### Task 1: The `aggregate_results` table

**Files:**
- Create: `supabase/migrations/20260929120000_add_aggregate_results.sql`
- Modify: `docs/pipeline_tables.sql` (append a table; the file currently
  ends with the commented-out `run_id` proposal)
- Test: `backend/tests/test_schema_sync.py` (add one test, widen one helper)

**Interfaces:**
- Consumes: nothing.
- Produces: the table `public.aggregate_results` with columns `id`,
  `run_id`, `generated_at`, `articles_in_run`, `corpus_articles`,
  `payload`. Tasks 4 and 6 write and read exactly these names.

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260929120000_add_aggregate_results.sql`:

```sql
-- One aggregated snapshot of the corpus per pipeline run.
--
-- The aggregation stage computes the /api/v1/results payload and stores
-- it here; the API serves the newest row. See docs/pipeline-coordinator.md.
--
-- WHY payload IS JSONB: the dashboard reads a fixed payload shape and no
-- filter UI exists yet, so one document per run is the whole contract.
-- A filtered query cannot be answered from a frozen snapshot -- when
-- FilterPanel lands, this either normalises or moves to per-request
-- aggregation. Recorded as an open question.
--
-- WHY run_id HAS NO FOREIGN KEY: backend/run_pipeline.py always keeps run
-- status in memory, never in pipeline_runs, so a `--live` demo run's
-- run_id names a run that was never recorded. A foreign key would make
-- the demo fail at its last stage.

create table if not exists public.aggregate_results (
  id              bigint generated by default as identity primary key,
  run_id          bigint,
  generated_at    timestamptz not null default now(),
  articles_in_run integer     not null default 0,
  corpus_articles integer     not null default 0,
  payload         jsonb       not null
);

-- The API only ever asks for the newest snapshot.
create index if not exists aggregate_results_generated_at_idx
  on public.aggregate_results (generated_at desc);
```

- [ ] **Step 2: Declare the table in the schema doc**

Append to `docs/pipeline_tables.sql`, after the commented-out `run_id`
proposal at the end of the file:

```sql
-- Aggregated dashboard snapshots, one per run. Applied as
-- supabase/migrations/20260929120000_add_aggregate_results.sql.
-- backend/agents/aggregation/db.py writes these columns and
-- backend/tests/test_schema_sync.py fails if the two drift apart.

create table if not exists public.aggregate_results (
  id              bigint generated by default as identity primary key,
  run_id          bigint,
  generated_at    timestamptz not null default now(),
  articles_in_run integer     not null default 0,
  corpus_articles integer     not null default 0,
  payload         jsonb       not null
);
```

- [ ] **Step 3: Write the failing schema-sync test**

`test_schema_sync.py` already has a `columns()` helper, but its regex
only matches `bigint|text|timestamptz|integer`, so it would silently
drop the `payload jsonb` column. Widen it and add the test.

In `backend/tests/test_schema_sync.py`, change the `columns` helper:

```python
def columns(block):
    return set(re.findall(r"^\s{2}(\w+)\s+(?:bigint|text|timestamptz|integer|jsonb)\b", block, re.M))
```

and append this test:

```python
def test_aggregate_results_columns_match_what_the_agent_writes(sql):
    """
    The aggregation agent writes these columns by name. A column renamed
    in one place and not the other is a 400 from PostgREST halfway
    through a run, which is a bad place to learn about it.
    """
    from agents.aggregation.db import AGGREGATE_COLUMNS

    assert columns(table(sql, "aggregate_results")) == {"id", *AGGREGATE_COLUMNS}
```

- [ ] **Step 4: Run it to verify it fails**

Run from `backend/`: `python -m pytest tests/test_schema_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agents.aggregation'`.
The three existing tests in the file still pass.

- [ ] **Step 5: Create the package and the column list**

Create empty `backend/agents/aggregation/__init__.py`.

Create `backend/agents/aggregation/db.py` with only the constant for
now — Task 4 fills in the rest:

```python
"""
Supabase reads and writes for the aggregation stage.

agents/aggregation/compute.py holds the aggregation rules; this file
only moves data. Filled in by Task 4 of the aggregation plan.
"""
from __future__ import annotations

AGGREGATE_TABLE = "aggregate_results"

# The columns write_snapshot() sends. tests/test_schema_sync.py checks
# docs/pipeline_tables.sql declares exactly these, plus id.
AGGREGATE_COLUMNS = (
    "run_id",
    "generated_at",
    "articles_in_run",
    "corpus_articles",
    "payload",
)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_schema_sync.py -v`
Expected: PASS, 4 tests. Suite total: **90 tests**.

Run from `backend/`: `python -m pytest tests -q`
Expected: 90 passed.

- [ ] **Step 7: Apply the migration to the live database**

`supabase db push` will refuse (see Global Constraints). Paste the
contents of the migration into the Supabase dashboard SQL editor and
run it, then confirm:

```
select count(*) from public.aggregate_results;
```

Expected: `0` — the table exists and is empty. If this step cannot be
done (no dashboard access), the rest of the plan still builds and its
tests still pass; only Task 9's live verification is blocked.

- [ ] **Step 8: Commit**

```bash
git add supabase/migrations/20260929120000_add_aggregate_results.sql \
        docs/pipeline_tables.sql \
        backend/agents/aggregation/__init__.py \
        backend/agents/aggregation/db.py \
        backend/tests/test_schema_sync.py
git commit -m "Add the aggregate_results table and keep it in sync"
```

---

### Task 2: The aggregation rules

Pure functions: rows in, dashboard payload out. No database, no clock.
This is the task that owns Review Focus items 2, 4 and 5.

**Files:**
- Create: `backend/agents/aggregation/compute.py`
- Test: `backend/tests/test_aggregation_compute.py`

**Interfaces:**
- Consumes: `AGGREGATE_COLUMNS` from Task 1 (not directly — only the
  column names it must produce values for).
- Produces, all in `agents.aggregation.compute`:
  - `SENTIMENT_LABELS: tuple[str, ...]` = `("positive", "neutral", "negative")`
  - `BASELINE_CLASSIFIER: str` = `"baseline_keyword"`
  - `TOP_TOPICS: int` = `10`, `ARTICLE_LIMIT: int` = `200`
  - `best_classification(rows: Iterable[dict]) -> dict[int, dict]`
  - `sentiment_distribution(rows: Sequence[dict], unavailable: str | None = None) -> dict`
  - `top_topics(rows: Sequence[dict], unavailable: str | None = None, limit: int = TOP_TOPICS) -> dict`
  - `article_rows(articles, classifications, topics, sentiments, limit=ARTICLE_LIMIT) -> list[dict]`
  - `build_payload(generated_at: str, run_id: int | None, articles, classification_rows, topic_rows, sentiment_rows, articles_in_run: int = 0, missing: dict[str, str] | None = None) -> dict`

  `build_payload` returns keys: `generated_at`, `run_id`,
  `corpus_articles`, `articles_in_run`, `classified_articles`,
  `sentiment_distribution`, `top_topics`, `articles`. Tasks 4, 5, 7 and
  8 depend on exactly these.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_aggregation_compute.py`:

```python
"""
The aggregation rules — rows in, dashboard payload out.

Everything here is a pure function call: no database, no fake client, no
clock. The decisions being checked are the ones that would otherwise
show up as a plausible-looking wrong number on the dashboard, which is
the failure mode this whole endpoint exists to end.
"""
import pytest

from agents.aggregation import compute


def article(id, title="A school adopts AI", source="EdSurge", published="2026-09-20T00:00:00+00:00"):
    return {"id": id, "title": title, "source": source, "url": f"https://edsurge.com/{id}",
            "published_date": published}


def classification(article_id, category="Administrator", classifier="baseline_keyword", confidence=0.5):
    return {"article_id": article_id, "stakeholder_category": category, "source_type": "trade",
            "confidence": confidence, "classifier": classifier}


# --- best_classification ----------------------------------------------
def test_one_row_per_article_even_with_two_classifiers():
    """
    classification_results is upserted on (article_id, classifier), so an
    article the keyword scorer AND the LLM both saw has two rows.
    Counting the table directly would count that article twice.
    """
    rows = [
        classification(1, "Educator", "baseline_keyword"),
        classification(1, "Administrator", "gpt-5.6-luna"),
        classification(2, "Student", "baseline_keyword"),
    ]
    best = compute.best_classification(rows)

    assert set(best) == {1, 2}
    # The LLM is the better classifier, so its row wins the tie.
    assert best[1]["stakeholder_category"] == "Administrator"


def test_between_two_rows_of_the_same_kind_the_confident_one_wins():
    rows = [
        classification(1, "Educator", "gpt-5.6-luna", confidence=0.4),
        classification(1, "Parent", "gpt-5.6-luna", confidence=0.9),
    ]
    assert compute.best_classification(rows)[1]["stakeholder_category"] == "Parent"


def test_a_row_with_no_article_id_is_skipped_not_counted_under_none():
    assert compute.best_classification([{"stakeholder_category": "Educator"}]) == {}


# --- sentiment_distribution -------------------------------------------
def test_sentiment_shares_are_fractions_of_the_rows_counted():
    rows = [{"article_id": i, "sentiment_label": label} for i, label in
            enumerate(["positive", "positive", "neutral", "negative"])]
    dist = compute.sentiment_distribution(rows)

    assert dist["available"] is True
    assert dist["positive"] == 0.5
    assert dist["neutral"] == 0.25
    assert dist["negative"] == 0.25
    assert dist["counted"] == 4


def test_labels_are_matched_case_and_space_insensitively():
    rows = [{"article_id": 1, "sentiment_label": " Positive "}]
    assert compute.sentiment_distribution(rows)["positive"] == 1.0


def test_an_unexpected_label_is_counted_under_other_not_dropped():
    rows = [{"article_id": 1, "sentiment_label": "positive"},
            {"article_id": 2, "sentiment_label": "mixed"}]
    dist = compute.sentiment_distribution(rows)

    assert dist["counted"] == 2
    assert dist["other"] == 1
    assert dist["positive"] == 0.5


def test_no_sentiment_rows_reports_unavailable_rather_than_zeros():
    """
    Zeros render as '0% positive, 0% neutral, 0% negative', which reads
    as a finding about the corpus instead of an empty table. The
    invented percentages the dashboard shows today are exactly what this
    endpoint exists to remove.
    """
    dist = compute.sentiment_distribution([])

    assert dist["available"] is False
    assert dist["reason"]
    assert dist["positive"] is None


def test_an_unreadable_table_reports_its_own_reason():
    dist = compute.sentiment_distribution([], unavailable="sentiment_results is not in the schema yet")
    assert dist["reason"] == "sentiment_results is not in the schema yet"


def test_available_and_unavailable_distributions_have_the_same_keys():
    """The front end renders one shape; a missing key is a crash there."""
    rows = [{"article_id": 1, "sentiment_label": "positive"}]
    assert set(compute.sentiment_distribution(rows)) == set(compute.sentiment_distribution([]))


# --- top_topics --------------------------------------------------------
def test_topics_are_ranked_most_frequent_first():
    rows = [{"article_id": i, "topic": topic} for i, topic in
            enumerate(["policy", "integrity", "policy", "tools", "policy", "integrity"])]
    topics = compute.top_topics(rows)

    assert topics["available"] is True
    assert topics["items"][0] == {"label": "policy", "count": 3}
    assert topics["items"][1] == {"label": "integrity", "count": 2}


def test_bertopic_outliers_are_not_a_topic():
    """
    BERTopic labels the articles it could not place '-1_...', and that
    bucket is usually the largest one — so it would top the chart.
    """
    rows = [{"article_id": i, "topic": "-1_students_ai_school"} for i in range(9)]
    rows.append({"article_id": 99, "topic": "academic integrity"})
    topics = compute.top_topics(rows)

    assert [i["label"] for i in topics["items"]] == ["academic integrity"]
    assert topics["counted"] == 1


def test_null_and_blank_topics_are_skipped():
    rows = [{"article_id": 1, "topic": None}, {"article_id": 2, "topic": "   "},
            {"article_id": 3, "topic": "policy"}]
    assert compute.top_topics(rows)["items"] == [{"label": "policy", "count": 1}]


def test_only_outlier_rows_reads_as_unavailable_not_as_an_empty_chart():
    rows = [{"article_id": i, "topic": "-1_a_b_c"} for i in range(5)]
    topics = compute.top_topics(rows)

    assert topics["available"] is False
    assert topics["items"] == []


def test_the_topic_list_is_capped():
    rows = [{"article_id": i, "topic": f"topic-{i}"} for i in range(30)]
    assert len(compute.top_topics(rows, limit=4)["items"]) == 4


def test_equally_common_topics_are_ordered_by_label_so_runs_are_reproducible():
    rows = [{"article_id": 1, "topic": "zebra"}, {"article_id": 2, "topic": "apple"}]
    assert [i["label"] for i in compute.top_topics(rows)["items"]] == ["apple", "zebra"]


# --- article_rows ------------------------------------------------------
def test_article_rows_join_the_analysis_a_row_has():
    articles = [article(1)]
    rows = compute.article_rows(
        articles,
        classifications=compute.best_classification([classification(1, "Educator")]),
        topics={1: "academic integrity"},
        sentiments={1: "positive"},
    )

    assert rows[0]["stakeholder"] == "Educator"
    assert rows[0]["topic"] == "academic integrity"
    assert rows[0]["sentiment"] == "positive"
    assert rows[0]["source"] == "EdSurge"


def test_an_article_with_no_analysis_still_appears_with_nulls():
    """
    The corpus is what was collected. Hiding the rows no agent has
    reached yet would make an unfinished pipeline look like a small one.
    """
    rows = compute.article_rows([article(1)], classifications={}, topics={}, sentiments={})

    assert len(rows) == 1
    assert rows[0]["stakeholder"] is None
    assert rows[0]["sentiment"] is None


def test_articles_come_back_newest_first():
    older = article(1, published="2026-01-01T00:00:00+00:00")
    newer = article(2, published="2026-09-01T00:00:00+00:00")
    rows = compute.article_rows([older, newer], {}, {}, {})

    assert [r["id"] for r in rows] == [2, 1]


def test_undated_articles_sort_last_instead_of_raising():
    """
    published_date is nullable — an RSS date that would not parse is
    stored as NULL (agents/collection/db.py) — and comparing a string
    with None raises TypeError.
    """
    undated = article(1, published=None)
    dated = article(2, published="2026-09-01T00:00:00+00:00")
    rows = compute.article_rows([undated, dated], {}, {}, {})

    assert [r["id"] for r in rows] == [2, 1]


def test_the_article_list_is_capped():
    articles = [article(i) for i in range(10)]
    assert len(compute.article_rows(articles, {}, {}, {}, limit=3)) == 3


# --- build_payload -----------------------------------------------------
def test_build_payload_has_every_key_the_dashboard_reads():
    payload = compute.build_payload(
        generated_at="2026-09-29T12:00:00+00:00",
        run_id=11,
        articles=[article(1)],
        classification_rows=[classification(1, "Educator")],
        topic_rows=[{"article_id": 1, "topic": "policy"}],
        sentiment_rows=[],
        articles_in_run=1,
        missing={"sentiment_results": "sentiment_results is not in the schema yet"},
    )

    assert set(payload) == {
        "generated_at", "run_id", "corpus_articles", "articles_in_run",
        "classified_articles", "sentiment_distribution", "top_topics", "articles",
    }
    assert payload["corpus_articles"] == 1
    assert payload["classified_articles"] == 1
    assert payload["top_topics"]["available"] is True
    assert payload["sentiment_distribution"]["available"] is False


def test_build_payload_over_an_empty_corpus_returns_a_payload_not_an_error():
    """
    A fresh database, or a run where every analysis stage failed. Dividing
    by a corpus of zero is the obvious way to turn that into a 500.
    """
    payload = compute.build_payload(
        generated_at="2026-09-29T12:00:00+00:00", run_id=None,
        articles=[], classification_rows=[], topic_rows=[], sentiment_rows=[],
    )

    assert payload["corpus_articles"] == 0
    assert payload["articles"] == []
    assert payload["sentiment_distribution"]["available"] is False
    assert payload["top_topics"]["available"] is False


def test_build_payload_does_not_double_count_a_twice_classified_article():
    payload = compute.build_payload(
        generated_at="2026-09-29T12:00:00+00:00", run_id=1,
        articles=[article(1)],
        classification_rows=[classification(1, "Educator", "baseline_keyword"),
                             classification(1, "Administrator", "gpt-5.6-luna")],
        topic_rows=[], sentiment_rows=[],
    )

    assert payload["classified_articles"] == 1
    assert payload["articles"][0]["stakeholder"] == "Administrator"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `python -m pytest tests/test_aggregation_compute.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute' from 'agents.aggregation'`.

- [ ] **Step 3: Write the implementation**

Create `backend/agents/aggregation/compute.py`:

```python
"""
Turning analysis rows into the dashboard payload. Pure functions only.

Nothing here touches Supabase, the network or the clock — the caller
passes `generated_at` in — so the aggregation rules can be tested
directly rather than through a fake database. agents/aggregation/db.py
does the reading and writing.

Every facet reports `available`. A facet with no rows comes back
available=False with a reason, never as zeros: '0% positive, 0% neutral,
0% negative' reads as a finding about the corpus rather than as an empty
table, and replacing figures that read like findings is the point of
this endpoint.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# The three labels the dashboard renders. A row with anything else is
# counted under "other" rather than silently dropped, so the totals add up.
SENTIMENT_LABELS = ("positive", "neutral", "negative")

# The keyword scorer's tag, as agents/adapters.py writes it.
# classification_results is upserted on (article_id, classifier), so one
# article can hold a baseline row AND an LLM row. The LLM is the better
# classifier, so the baseline row is used only when it is the only one.
BASELINE_CLASSIFIER = "baseline_keyword"

TOP_TOPICS = 10

# No filter UI exists, so the article table is the newest slice of the
# corpus rather than all of it. The payload reports corpus_articles
# alongside, so the dashboard can say "showing 200 of 814".
ARTICLE_LIMIT = 200

# BERTopic names its outlier cluster "-1_students_ai_school": articles it
# could not place. That bucket is usually the largest, so leaving it in
# would put "could not classify" at the top of the chart.
OUTLIER_TOPIC_PREFIX = "-1"


# --- classification ----------------------------------------------------
def best_classification(rows: Iterable[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    """
    One classification row per article, keyed by article_id.

    classification_results holds up to one row per classifier per
    article, so counting the table directly counts a twice-classified
    article twice. The LLM row wins over the keyword row; between two of
    the same kind, the more confident one wins.
    """
    best: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        article_id = row.get("article_id")
        if article_id is None:
            continue
        current = best.get(article_id)
        if current is None or _rank(row) < _rank(current):
            best[article_id] = row
    return best


def _rank(row: Dict[str, Any]) -> Tuple[int, float]:
    """Lower sorts better: a real classifier first, then higher confidence."""
    is_baseline = row.get("classifier") == BASELINE_CLASSIFIER
    confidence = row.get("confidence")
    numeric = float(confidence) if isinstance(confidence, (int, float)) else 0.0
    return (1 if is_baseline else 0, -numeric)


# --- facets ------------------------------------------------------------
def sentiment_distribution(
    rows: Sequence[Dict[str, Any]], unavailable: Optional[str] = None
) -> Dict[str, Any]:
    """Share of analysed articles at each sentiment label."""
    labels = [str(r.get("sentiment_label") or "").strip().lower() for r in rows]
    counted = [label for label in labels if label]

    if unavailable or not counted:
        return {
            "available": False,
            "reason": unavailable or "sentiment_results has no rows yet",
            "counted": 0,
            "other": 0,
            **{label: None for label in SENTIMENT_LABELS},
        }

    total = len(counted)
    known = {label: counted.count(label) for label in SENTIMENT_LABELS}
    return {
        "available": True,
        "reason": None,
        "counted": total,
        "other": total - sum(known.values()),
        **{label: count / total for label, count in known.items()},
    }


def top_topics(
    rows: Sequence[Dict[str, Any]],
    unavailable: Optional[str] = None,
    limit: int = TOP_TOPICS,
) -> Dict[str, Any]:
    """The most common topic labels, most frequent first."""
    counts: Dict[str, int] = {}
    for row in rows:
        label = str(row.get("topic") or "").strip()
        if not label or label.startswith(OUTLIER_TOPIC_PREFIX):
            continue
        counts[label] = counts.get(label, 0) + 1

    if unavailable or not counts:
        return {
            "available": False,
            "reason": unavailable or "topic_results has no usable rows yet",
            "counted": 0,
            "items": [],
        }

    # Count descending, then label ascending, so two equally common
    # topics come back in the same order on every run.
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
    return {
        "available": True,
        "reason": None,
        "counted": sum(counts.values()),
        "items": [{"label": label, "count": count} for label, count in ranked],
    }


def article_rows(
    articles: Sequence[Dict[str, Any]],
    classifications: Dict[int, Dict[str, Any]],
    topics: Dict[int, Optional[str]],
    sentiments: Dict[int, Optional[str]],
    limit: int = ARTICLE_LIMIT,
) -> List[Dict[str, Any]]:
    """
    The article table the dashboard renders, newest first.

    An article with no analysis row still appears, with null in that
    column: the corpus is what was collected, and hiding the rows no
    agent has reached yet would make an unfinished pipeline look like a
    small one.
    """
    ordered = sorted(articles, key=_published_key, reverse=True)
    rows = []
    for item in ordered[:limit]:
        article_id = item.get("id")
        classification = classifications.get(article_id) or {}
        rows.append({
            "id": article_id,
            "title": item.get("title"),
            "source": item.get("source"),
            "url": item.get("url"),
            "published_date": item.get("published_date"),
            "stakeholder": classification.get("stakeholder_category"),
            "source_type": classification.get("source_type"),
            "topic": topics.get(article_id),
            "sentiment": sentiments.get(article_id),
        })
    return rows


def _published_key(article: Dict[str, Any]) -> Tuple[int, str]:
    """
    Sort key for newest-first, with undated articles last.

    published_date is nullable — an RSS date that would not parse is
    stored as NULL — and comparing a string with None raises TypeError,
    so the flag is sorted on before the value.
    """
    published = article.get("published_date")
    return (1 if published else 0, str(published or ""))


# --- the payload -------------------------------------------------------
def build_payload(
    generated_at: str,
    run_id: Optional[int],
    articles: Sequence[Dict[str, Any]],
    classification_rows: Sequence[Dict[str, Any]],
    topic_rows: Sequence[Dict[str, Any]],
    sentiment_rows: Sequence[Dict[str, Any]],
    articles_in_run: int = 0,
    missing: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    The whole /api/v1/results payload.

    `missing` maps a table name to why it could not be read, for the
    tables no agent writes yet. Those facets come back available=False
    with the reason and the rest of the payload is still built: a
    pipeline with three real agents should show three agents' worth of
    findings, not an error.
    """
    missing = missing or {}
    classifications = best_classification(classification_rows)
    topics = {
        r["article_id"]: r.get("topic")
        for r in topic_rows
        if r.get("article_id") is not None
    }
    sentiments = {
        r["article_id"]: r.get("sentiment_label")
        for r in sentiment_rows
        if r.get("article_id") is not None
    }

    return {
        "generated_at": generated_at,
        "run_id": run_id,
        "corpus_articles": len(articles),
        "articles_in_run": articles_in_run,
        "classified_articles": len(classifications),
        "sentiment_distribution": sentiment_distribution(
            sentiment_rows, unavailable=missing.get("sentiment_results")
        ),
        "top_topics": top_topics(topic_rows, unavailable=missing.get("topic_results")),
        "articles": article_rows(articles, classifications, topics, sentiments),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_aggregation_compute.py -v`
Expected: PASS, 23 tests. Suite total: **113 tests**.

- [ ] **Step 5: Type check**

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/aggregation/compute.py backend/tests/test_aggregation_compute.py
git commit -m "Add the aggregation rules as pure functions"
```

---

### Task 3: A shared fake Supabase client for the tests

The fake client lives inside `test_agent_adapters.py` today. The
aggregation tests need it too, plus `insert`, `range` and real ordering.
Moving it is a pure refactor with all 113 tests as the gate.

**Files:**
- Create: `backend/tests/fakes.py`
- Modify: `backend/tests/test_agent_adapters.py:21-82` (delete
  `FakeQuery`, `FakeClient` and the `fake_client` fixture; import instead)
- Modify: `backend/tests/conftest.py` (add the shared `fake_client` fixture)

**Interfaces:**
- Consumes: nothing.
- Produces, in `tests/fakes.py`: `FakeQuery`, `FakeClient(**tables)`,
  `MissingTableClient(missing=(), **tables)`. And in `conftest.py`, the
  fixture `fake_client(module=None, client=None, **tables) -> FakeClient`,
  which patches `get_client` on `module` (default `agents.adapters`) and
  returns the fake. Tasks 4, 5 and 6 use it.

- [ ] **Step 1: Create the fake, extended**

Create `backend/tests/fakes.py`:

```python
"""
A fake Supabase client for the tests that talk to the database.

The agents and the stores reach Supabase through the PostgREST-style
builder (`client.table(name).select(...).eq(...).execute()`). This
stands in for it with dicts in memory, so the suite can check the
decisions a module makes about rows without a network or credentials.

It implements only what the code under test calls. Add a method when a
new call appears rather than making it general: a fake that quietly
accepted a filter it does not apply would make a broken query look like
a passing test.
"""
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, tables, name):
        self.tables, self.name = tables, name
        self.rows = tables.setdefault(name, [])
        self.columns = "*"
        self.filters, self.in_filter = [], None
        self.max_rows, self.upserted, self.inserted = None, None, None
        self.order_by, self.descending = None, False
        self.range_from, self.range_to = None, None

    def select(self, columns):
        self.columns = columns
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filter = (column, set(values))
        return self

    def order(self, column, desc=False):
        self.order_by, self.descending = column, desc
        return self

    def limit(self, count):
        self.max_rows = count
        return self

    def range(self, start, end):
        """PostgREST's inclusive row range, called as .range(0, 999)."""
        self.range_from, self.range_to = start, end
        return self

    def upsert(self, rows, on_conflict=None, ignore_duplicates=False):
        self.upserted = rows if isinstance(rows, list) else [rows]
        return self

    def insert(self, rows):
        self.inserted = rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        if self.inserted is not None:
            # Identity columns are assigned by the database, and callers
            # read the id back off the returned row.
            written = [dict(r, id=len(self.rows) + i + 1) for i, r in enumerate(self.inserted)]
            self.rows.extend(written)
            return SimpleNamespace(data=[dict(r) for r in written])
        if self.upserted is not None:
            self.rows.extend(self.upserted)
            return SimpleNamespace(data=list(self.upserted))

        matches = [r for r in self.rows if all(r.get(c) == v for c, v in self.filters)]
        if self.in_filter:
            column, values = self.in_filter
            matches = [r for r in matches if r.get(column) in values]
        if self.order_by:
            # Nulls last ascending, as Postgres does, and comparing a
            # value with None would raise.
            matches = sorted(
                matches,
                key=lambda r: (r.get(self.order_by) is None, r.get(self.order_by) or ""),
                reverse=self.descending,
            )
        if self.range_from is not None:
            matches = matches[self.range_from : self.range_to + 1]
        if self.max_rows is not None:
            matches = matches[: self.max_rows]
        return SimpleNamespace(data=[dict(r) for r in matches])


class FakeClient:
    def __init__(self, **tables):
        self.tables = {name: list(rows) for name, rows in tables.items()}

    def table(self, name):
        return FakeQuery(self.tables, name)


class _MissingTableQuery(FakeQuery):
    def execute(self):
        raise RuntimeError(f'relation "public.{self.name}" does not exist')


class MissingTableClient(FakeClient):
    """
    Fails the way PostgREST does for a table that is not in the schema.

    sentiment_results and stance_results have no agent on any branch, so
    aggregation has to cope with them being absent rather than empty —
    and 'absent' arrives as an error at execute() time, not as zero rows.
    """

    def __init__(self, missing=(), **tables):
        super().__init__(**tables)
        self.missing = set(missing)

    def table(self, name):
        if name in self.missing:
            return _MissingTableQuery(self.tables, name)
        return super().table(name)
```

- [ ] **Step 2: Add the shared fixture**

Append to `backend/tests/conftest.py`:

```python
@pytest.fixture
def fake_client(monkeypatch):
    """
    Point a module's get_client() at a fake Supabase client.

        fake_client(articles=[...])                      # agents.adapters
        fake_client(module=db, articles=[...])           # another module
        fake_client(module=db, client=MissingTableClient(missing=["x"]))

    Returns the fake, so a test can read back what was written to it.
    """

    def install(module=None, client=None, **tables):
        from fakes import FakeClient

        if module is None:
            from agents import adapters as module
        built = client if client is not None else FakeClient(**tables)
        monkeypatch.setattr(module, "get_client", lambda: built)
        return built

    return install
```

- [ ] **Step 3: Point the adapter tests at the shared fake**

In `backend/tests/test_agent_adapters.py`, delete the `FakeQuery` and
`FakeClient` class definitions and the local `fake_client` fixture
(lines 21-82, from `# --- a fake Supabase client` down to the end of the
fixture), and delete the now-unused `from types import SimpleNamespace`
import. The module keeps its remaining imports and gains nothing: the
fixture now comes from `conftest.py`, and its call signature is
unchanged for these tests.

- [ ] **Step 4: Run the whole suite to verify the move changed nothing**

Run from `backend/`: `python -m pytest tests -q`
Expected: 113 passed. Any failure here is a transcription error in the
move, not a new behaviour.

- [ ] **Step 5: Type check**

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fakes.py backend/tests/conftest.py backend/tests/test_agent_adapters.py
git commit -m "Share the fake Supabase client between test modules"
```

---

### Task 4: Reading the corpus and writing the snapshot

This task owns Review Focus items 1 and 3.

**Files:**
- Modify: `backend/agents/aggregation/db.py` (created as a stub in Task 1)
- Test: `backend/tests/test_aggregation_agent.py`

**Interfaces:**
- Consumes: `AGGREGATE_TABLE`, `AGGREGATE_COLUMNS` (Task 1);
  `get_client` from `agents.supabase_client`; the `fake_client` fixture
  and `MissingTableClient` (Task 3).
- Produces, in `agents.aggregation.db`:
  - `PAGE: int` = `1000`
  - `read_optional(table: str, columns: str, order_by: str) -> tuple[list[dict], str | None]`
  - `read_corpus() -> dict` with keys `articles`, `classification_rows`,
    `topic_rows`, `sentiment_rows`, `missing`
  - `write_snapshot(run_id: int | None, payload: dict, articles_in_run: int) -> dict`

  Task 5 calls `read_corpus()` and `write_snapshot()`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_aggregation_agent.py`:

```python
"""
The aggregation agent's database layer and its adapter.

Everything here runs against the fake Supabase client in tests/fakes.py.
These tests check what the agent asks the database for and what it does
with the answer — including the two answers that are easy to get wrong:
a table that holds more rows than one PostgREST request returns, and a
table that is not in the schema at all.
"""
from types import SimpleNamespace

import pytest

from agents.aggregation import db
from fakes import FakeClient, MissingTableClient


def article(id, relevant=True, status="success", published="2026-09-20T00:00:00+00:00"):
    return {"id": id, "title": f"Article {id}", "source": "EdSurge",
            "url": f"https://edsurge.com/{id}", "published_date": published,
            "is_relevant": relevant, "processing_status": status}


# --- paging ------------------------------------------------------------
def test_reads_past_the_thousand_row_response_limit(fake_client):
    """
    PostgREST returns at most 1000 rows per request whatever the query
    asks for. The corpus was 814 articles in September 2026, so the first
    run after it crosses 1000 would aggregate a subset and publish it as
    the whole picture, with no error anywhere.
    """
    fake_client(module=db, articles=[article(i) for i in range(1, 2451)])

    assert len(db.read_corpus()["articles"]) == 2450


def test_a_corpus_smaller_than_one_page_is_read_in_one_request(fake_client):
    client = fake_client(module=db, articles=[article(1), article(2)])
    assert len(db.read_corpus()["articles"]) == 2


# --- which articles count ---------------------------------------------
def test_only_analysable_articles_are_counted(fake_client):
    """
    The same articles collection hands to analysis: marked relevant and
    preprocessed successfully. An article whose page never downloaded has
    no clean_content and so no analysis rows — counting it would deflate
    every percentage.
    """
    fake_client(module=db, articles=[
        article(1),
        article(2, relevant=False),
        article(3, status="failed"),
    ])

    assert [a["id"] for a in db.read_corpus()["articles"]] == [1]


# --- a table that is not in the schema --------------------------------
def test_a_missing_sentiment_table_is_reported_not_raised(fake_client):
    """
    No sentiment agent exists on any branch, so sentiment_results may not
    be in the schema. Raising would fail the aggregation stage on every
    run and leave every run at completed_with_errors.
    """
    fake_client(module=db, client=MissingTableClient(
        missing=["sentiment_results"], articles=[article(1)],
    ))
    corpus = db.read_corpus()

    assert corpus["sentiment_rows"] == []
    assert "sentiment_results" in corpus["missing"]
    assert corpus["articles"]      # the rest was still read


def test_a_missing_topic_table_is_reported_too(fake_client):
    fake_client(module=db, client=MissingTableClient(
        missing=["topic_results"], articles=[article(1)],
    ))
    assert "topic_results" in db.read_corpus()["missing"]


def test_an_error_that_is_not_a_missing_table_is_raised(fake_client):
    """
    read_optional tolerates a table that is not in the schema. It must not
    tolerate anything else: swallowing a 42501 would turn a publishable
    key into a dashboard that quietly reports no sentiment. Note how close
    the two codes are — 42501 is permission denied, 42P01 is undefined
    table — which is the reason this test exists.
    """
    class Denied(FakeClient):
        def table(self, name):
            if name == "sentiment_results":
                raise RuntimeError("42501 permission denied for table sentiment_results")
            return super().table(name)

    fake_client(module=db, client=Denied(
        articles=[article(1)], classification_results=[], topic_results=[],
    ))
    with pytest.raises(RuntimeError, match="42501"):
        db.read_corpus()


def test_a_missing_articles_table_is_not_tolerated(fake_client):
    """
    articles is not optional. An absent corpus is a broken deployment,
    not a facet to mark unavailable.
    """
    fake_client(module=db, client=MissingTableClient(missing=["articles"]))
    with pytest.raises(RuntimeError, match="does not exist"):
        db.read_corpus()


# --- writing the snapshot ---------------------------------------------
def test_write_snapshot_stores_the_columns_the_schema_declares(fake_client):
    client = fake_client(module=db)
    payload = {"generated_at": "2026-09-29T12:00:00+00:00", "corpus_articles": 814}

    written = db.write_snapshot(run_id=11, payload=payload, articles_in_run=104)

    assert set(written) == {"id", *db.AGGREGATE_COLUMNS}
    assert written["run_id"] == 11
    assert written["articles_in_run"] == 104
    assert written["corpus_articles"] == 814
    assert written["payload"] == payload
    assert len(client.tables[db.AGGREGATE_TABLE]) == 1


def test_snapshots_accumulate_rather_than_overwriting_each_other(fake_client):
    """
    A history, not a single current row: the dashboard shows the newest,
    and a failed run's snapshot stays visible instead of vanishing.
    """
    client = fake_client(module=db)
    db.write_snapshot(1, {"generated_at": "2026-09-29T12:00:00+00:00", "corpus_articles": 1}, 1)
    db.write_snapshot(2, {"generated_at": "2026-09-29T13:00:00+00:00", "corpus_articles": 2}, 1)

    assert len(client.tables[db.AGGREGATE_TABLE]) == 2


def test_a_snapshot_insert_that_returns_nothing_raises(fake_client):
    """
    PostgREST accepting an insert and returning no row normally means the
    key may INSERT but not SELECT. Saying so beats an IndexError.
    """
    class Silent(FakeClient):
        def table(self, name):
            query = super().table(name)
            query.execute = lambda: SimpleNamespace(data=[])
            return query

    fake_client(module=db, client=Silent())
    with pytest.raises(RuntimeError, match="returned no row"):
        db.write_snapshot(1, {"generated_at": "x", "corpus_articles": 0}, 0)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `python -m pytest tests/test_aggregation_agent.py -v`
Expected: FAIL — `AttributeError: module 'agents.aggregation.db' has no attribute 'read_corpus'`.

- [ ] **Step 3: Write the implementation**

Replace the body of `backend/agents/aggregation/db.py` (keep the two
constants from Task 1):

```python
"""
Supabase reads and writes for the aggregation stage.

Reads the corpus and the analysis tables, writes one snapshot row to
aggregate_results. agents/aggregation/compute.py holds the aggregation
rules; this file only moves data.

WHY THE WHOLE CORPUS, NOT THE RUN'S ARTICLES
The agent contract says a stage stays inside the IDs it was given
(docs/pipeline-coordinator.md, rule 8). Aggregation is the one stage
where that would be wrong: the dashboard shows the state of the whole
corpus, and a run that collected 40 new articles must not replace an
814-article picture with a 40-article one. The snapshot records the run
that produced it and how many articles that run contributed, so the two
numbers stay tellable apart. Recorded as an open question in
docs/pipeline-coordinator.md.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..supabase_client import get_client

logger = logging.getLogger(__name__)

# PostgREST returns at most 1000 rows per request whatever the query asks
# for, so every read here pages with .range(). The corpus passed 814
# articles in September 2026; without paging, the first run after it
# crosses 1000 would quietly aggregate a subset and publish it as the
# whole picture.
PAGE = 1000

AGGREGATE_TABLE = "aggregate_results"

# The columns write_snapshot() sends. tests/test_schema_sync.py checks
# docs/pipeline_tables.sql declares exactly these, plus id.
AGGREGATE_COLUMNS = (
    "run_id",
    "generated_at",
    "articles_in_run",
    "corpus_articles",
    "payload",
)

# A table no agent writes yet is absent from the schema, and PostgREST
# reports that as an error rather than as an empty result.
MISSING_TABLE_SIGNS = (
    "42p01",
    "does not exist",
    "could not find the table",
    "undefined_table",
)


def _page_through(
    table: str,
    columns: str,
    order_by: str,
    where: Sequence[Tuple[str, Any]] = (),
) -> List[Dict[str, Any]]:
    """Every row of `table`, a page at a time."""
    client = get_client()
    rows: List[Dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(columns)
        for column, value in where:
            query = query.eq(column, value)
        result = query.order(order_by).range(start, start + PAGE - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        start += PAGE


def read_optional(
    table: str, columns: str, order_by: str
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Rows from a table that may not exist yet, and why if it does not.

    sentiment_results and stance_results have no agent on any branch, so
    they may not be in the schema at all. Aggregating without them is the
    honest answer — the payload marks the facet unavailable — whereas
    raising would fail the stage on every run and leave every run at
    completed_with_errors. Any other error is re-raised: the contract is
    that a real failure reaches the coordinator.
    """
    try:
        return _page_through(table, columns, order_by), None
    except Exception as exc:
        detail = str(getattr(exc, "message", "") or exc).lower()
        if any(sign in detail for sign in MISSING_TABLE_SIGNS):
            logger.warning("%s is not in the schema yet; aggregating without it", table)
            return [], f"{table} is not in the schema yet"
        raise


def read_corpus() -> Dict[str, Any]:
    """
    Everything the payload is built from, one paged read per table.

    `articles` is filtered to what analysis was actually given: marked
    relevant and preprocessed successfully. An irrelevant article, or one
    whose page could not be downloaded, has no clean_content and so no
    analysis rows; counting it would deflate every percentage.

    articles and classification_results are read without tolerance: both
    exist and both have rows. An absent corpus is a broken deployment,
    not a facet to mark unavailable.
    """
    articles = _page_through(
        "articles",
        "id, title, source, url, published_date",
        "id",
        where=(("is_relevant", True), ("processing_status", "success")),
    )
    classification_rows = _page_through(
        "classification_results",
        "article_id, stakeholder_category, source_type, confidence, classifier",
        "article_id",
    )
    topic_rows, topic_missing = read_optional("topic_results", "article_id, topic", "article_id")
    sentiment_rows, sentiment_missing = read_optional(
        "sentiment_results", "article_id, sentiment_label", "article_id"
    )

    missing = {
        table: reason
        for table, reason in (
            ("topic_results", topic_missing),
            ("sentiment_results", sentiment_missing),
        )
        if reason
    }
    logger.info(
        "Aggregation read %d article(s), %d classification row(s), %d topic row(s), "
        "%d sentiment row(s)%s",
        len(articles), len(classification_rows), len(topic_rows), len(sentiment_rows),
        f"; unavailable: {', '.join(sorted(missing))}" if missing else "",
    )
    return {
        "articles": articles,
        "classification_rows": classification_rows,
        "topic_rows": topic_rows,
        "sentiment_rows": sentiment_rows,
        "missing": missing,
    }


def write_snapshot(
    run_id: Optional[int], payload: Dict[str, Any], articles_in_run: int
) -> Dict[str, Any]:
    """
    Store one snapshot row and return it as stored.

    Insert, not upsert: the snapshots are a history, one per run, so the
    dashboard can show the latest while a failed run's row stays visible
    rather than being overwritten by the next one.
    """
    row = {
        "run_id": run_id,
        "generated_at": payload["generated_at"],
        "articles_in_run": articles_in_run,
        "corpus_articles": payload["corpus_articles"],
        "payload": payload,
    }
    result = get_client().table(AGGREGATE_TABLE).insert(row).execute()
    written = (getattr(result, "data", None) or [None])[0]
    if written is None:
        raise RuntimeError(
            f"{AGGREGATE_TABLE}: insert returned no row, so nothing was stored for "
            f"run {run_id}. Check that SUPABASE_KEY has INSERT and SELECT on "
            f"{AGGREGATE_TABLE} — the publishable key has neither."
        )
    return written
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_aggregation_agent.py -v`
Expected: PASS, 10 tests. Suite total: **123 tests**.

- [ ] **Step 5: Type check**

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/aggregation/db.py backend/tests/test_aggregation_agent.py
git commit -m "Read the corpus in pages and store the aggregated snapshot"
```

---

### Task 5: The `AggregationAgent` adapter and registry wiring

**Files:**
- Modify: `backend/agents/adapters.py` (append the class; update the
  "Which stages are real" list in the module docstring at lines 19-29)
- Modify: `backend/orchestrator/registry.py:85-114` (register in the
  `live` branch; remove the aggregation stub registration)
- Test: `backend/tests/test_aggregation_agent.py` (append)
- Test: `backend/tests/test_registry_wiring.py:25-26` (move `AGGREGATION`
  out of `STILL_STUBBED`)

**Interfaces:**
- Consumes: `read_corpus()`, `write_snapshot()` (Task 4);
  `build_payload()` (Task 2); `Agent`, `RunContext` from `orchestrator`.
- Produces: `agents.adapters.AggregationAgent` with `name = "aggregation"`
  and `run(ctx) -> dict` returning keys `aggregated`, `articles_in_run`,
  `from_stages`, `top_topics`, `unavailable`. Registered for the
  `AGGREGATION` stage when `live` is true.

- [ ] **Step 1: Write the failing tests**

First add to the import block at the top of
`backend/tests/test_aggregation_agent.py`:

```python
from agents.adapters import AggregationAgent
from orchestrator.models import RunContext
from orchestrator.stages import CLASSIFICATION, TOPIC
```

Then append the tests to the same file:

```python
# --- the adapter -------------------------------------------------------
@pytest.fixture
def agent_client(fake_client):
    """
    The adapter reads and writes through agents/aggregation/db.py, so that
    is the module whose get_client is replaced — not agents.adapters.
    """
    def install(client=None, **tables):
        return fake_client(module=db, client=client, **tables)

    return install


def test_the_agent_stores_a_snapshot_of_the_whole_corpus(agent_client):
    client = agent_client(
        # Article 1 is the newer one, so it sorts first and the assertion
        # below does not depend on how two equal dates happen to tie-break.
        articles=[article(1, published="2026-09-21T00:00:00+00:00"),
                  article(2, published="2026-09-20T00:00:00+00:00")],
        classification_results=[{"article_id": 1, "stakeholder_category": "Educator",
                                 "source_type": "trade", "confidence": 0.8,
                                 "classifier": "baseline_keyword"}],
        topic_results=[{"article_id": 1, "topic": "academic integrity"}],
        sentiment_results=[],
    )
    ctx = RunContext(run_id=11, article_ids=[2], approved_ids=[2],
                     completed_analysis=[TOPIC, CLASSIFICATION])

    output = AggregationAgent().run(ctx)

    assert output["aggregated"] == 2          # the corpus, not the run
    assert output["articles_in_run"] == 1     # what this run contributed
    assert output["from_stages"] == [TOPIC, CLASSIFICATION]
    assert output["top_topics"] == 1

    stored = client.tables[db.AGGREGATE_TABLE]
    assert len(stored) == 1
    assert stored[0]["run_id"] == 11
    assert stored[0]["payload"]["corpus_articles"] == 2
    assert stored[0]["payload"]["articles"][0]["stakeholder"] == "Educator"


def test_the_agent_succeeds_with_no_sentiment_table(agent_client):
    """
    Review Focus 3, end to end: a stage that failed on every run because a
    teammate has not started is a stage nobody can read a run status from.
    """
    agent_client(client=MissingTableClient(
        missing=["sentiment_results"],
        articles=[article(1)],
        classification_results=[],
        topic_results=[{"article_id": 1, "topic": "policy"}],
    ))
    output = AggregationAgent().run(RunContext(run_id=1, approved_ids=[1]))

    assert output["unavailable"] == ["sentiment_results"]
    assert output["aggregated"] == 1


def test_the_agent_stores_a_snapshot_for_an_empty_corpus(agent_client):
    client = agent_client(articles=[], classification_results=[],
                          topic_results=[], sentiment_results=[])
    output = AggregationAgent().run(RunContext(run_id=1))

    assert output["aggregated"] == 0
    assert client.tables[db.AGGREGATE_TABLE][0]["payload"]["articles"] == []


def test_the_agent_raises_rather_than_reporting_an_empty_success(agent_client):
    """
    Contract rule 6: raise on failure. A read that fails for a reason
    other than a missing table must reach the coordinator so it retries.
    """
    class Broken(FakeClient):
        def table(self, name):
            raise RuntimeError("42501 permission denied for table articles")

    agent_client(client=Broken())
    with pytest.raises(RuntimeError, match="42501"):
        AggregationAgent().run(RunContext(run_id=1))


def test_the_snapshot_payload_is_what_the_endpoint_will_serve(agent_client):
    """The agent must not reshape what compute.build_payload produced."""
    from agents.aggregation import compute

    client = agent_client(articles=[article(1)], classification_results=[],
                          topic_results=[], sentiment_results=[])
    AggregationAgent().run(RunContext(run_id=1, approved_ids=[1]))

    reference = compute.build_payload(
        generated_at="x", run_id=1, articles=[], classification_rows=[],
        topic_rows=[], sentiment_rows=[],
    )
    assert set(client.tables[db.AGGREGATE_TABLE][0]["payload"]) == set(reference)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `python -m pytest tests/test_aggregation_agent.py -v`
Expected: FAIL at import — `ImportError: cannot import name 'AggregationAgent' from 'agents.adapters'`.

- [ ] **Step 3: Write the adapter**

Append to `backend/agents/adapters.py`:

```python
# ---------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------
class AggregationAgent(Agent):
    """
    Turn the analysis tables into the dashboard payload and store it.

    Unlike every other stage, this one reads the whole analysable corpus
    rather than ctx.approved_ids. The dashboard shows the state of the
    corpus, not of one run: a run that collected 40 articles must not
    replace an 814-article picture with a 40-article one. ctx says which
    run to attribute the snapshot to and how many articles that run
    contributed, so the two numbers stay tellable apart. The reasoning is
    in agents/aggregation/db.py; it is an open question in
    docs/pipeline-coordinator.md.

    A table with no agent yet — sentiment_results above all — is reported
    as unavailable in the payload rather than failing the stage. A stage
    that failed on every run because a teammate has not started is a
    stage nobody can read a run status from. Any other database error is
    raised, as the contract requires.
    """

    name = "aggregation"

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        from datetime import datetime, timezone

        from .aggregation import compute, db

        corpus = db.read_corpus()
        articles_in_run = len(ctx.approved_ids)
        payload = compute.build_payload(
            generated_at=datetime.now(timezone.utc).isoformat(),
            run_id=ctx.run_id,
            articles=corpus["articles"],
            classification_rows=corpus["classification_rows"],
            topic_rows=corpus["topic_rows"],
            sentiment_rows=corpus["sentiment_rows"],
            articles_in_run=articles_in_run,
            missing=corpus["missing"],
        )
        db.write_snapshot(ctx.run_id, payload, articles_in_run)

        unavailable = sorted(corpus["missing"])
        logger.info(
            "Run %s: aggregated %d article(s) from %s%s",
            ctx.run_id,
            payload["corpus_articles"],
            ", ".join(ctx.completed_analysis) or "no analysis stages",
            f"; unavailable: {', '.join(unavailable)}" if unavailable else "",
        )
        return {
            "aggregated": payload["corpus_articles"],
            "articles_in_run": articles_in_run,
            "from_stages": list(ctx.completed_analysis),
            "top_topics": len(payload["top_topics"]["items"]),
            "unavailable": unavailable,
        }
```

Then update the "Which stages are real" list in the module docstring:
change the `aggregation` line from

```
      aggregation     stub - no implementation yet
```

to

```
      aggregation     real - AggregationAgent
```

- [ ] **Step 4: Register it**

In `backend/orchestrator/registry.py`, add `AggregationAgent` to the
import inside the `live` branch and register it there:

```python
    if live:
        from agents.adapters import (
            AggregationAgent,
            ClassificationAgent,
            CollectionAgent,
            SecurityAgent,
        )

        logger.info(
            "Registry: real agents for collection, security, classification and aggregation"
        )
        registry.register(COLLECTION, CollectionAgent(**collection_options))
        registry.register(SECURITY, SecurityAgent())
        registry.register(AGGREGATION, AggregationAgent())
```

(the classification block below it is unchanged), and in the `else`
branch add the aggregation stub that moves out of the shared tail:

```python
    else:
        logger.info("Registry: stub agents (Supabase not configured)")
        registry.register(COLLECTION, agents.stub_collection())
        registry.register(SECURITY, agents.stub_security())
        registry.register(CLASSIFICATION, agents.stub_analysis(CLASSIFICATION))
        registry.register(AGGREGATION, agents.stub_aggregation())
```

Then delete the now-duplicated line from the shared tail:

```python
    registry.register(AGGREGATION, agents.stub_aggregation())
```

- [ ] **Step 5: Update the registry-wiring test**

In `backend/tests/test_registry_wiring.py`, move `AGGREGATION` from
`STILL_STUBBED` to `REAL_STAGES`:

```python
REAL_STAGES = (COLLECTION, SECURITY, CLASSIFICATION, AGGREGATION)
STILL_STUBBED = (SENTIMENT, TOPIC, STANCE)
```

and update the docstring of `test_stages_with_no_implementation_stay_stubbed_even_when_live`:

```python
def test_stages_with_no_implementation_stay_stubbed_even_when_live():
    """
    sentiment and stance have no implementation on any branch, and the
    topic model needs ~2GB of ML libraries. Asking for live agents must
    not quietly register something for them. Aggregation is no longer on
    this list — it is real as of the aggregation agent.
    """
```

- [ ] **Step 6: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_aggregation_agent.py tests/test_registry_wiring.py -v`
Expected: PASS, 15 aggregation tests + the registry tests.

Run from `backend/`: `python -m pytest tests -q`
Expected: 128 passed. Suite total: **128 tests**.

- [ ] **Step 7: See it run with stubs and then for real**

Run from `backend/`: `python run_pipeline.py`
Expected: seven stages, `aggregation succeeded`, result `completed`.
Stubs everywhere, so no database is touched.

Run from `backend/`: `python run_pipeline.py --live --backlog`
Expected: `aggregation succeeded`, and a new row in `aggregate_results`.
Check it in the dashboard SQL editor:

```sql
select id, run_id, corpus_articles, articles_in_run, generated_at
  from public.aggregate_results order by id desc limit 1;
```

This is also the check that Design Decision 4 holds: `run_pipeline.py`
keeps runs in memory, so this row's `run_id` names a run that is not in
`pipeline_runs`. With a foreign key it would have failed here.

- [ ] **Step 8: Type check**

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

- [ ] **Step 9: Commit**

```bash
git add backend/agents/adapters.py backend/orchestrator/registry.py \
        backend/tests/test_aggregation_agent.py backend/tests/test_registry_wiring.py
git commit -m "Wire the aggregation agent into the pipeline"
```

---

### Task 6: The results store

**Files:**
- Create: `backend/orchestrator/results_store.py`
- Modify: `backend/orchestrator/__init__.py` (export the new names)
- Test: `backend/tests/test_results_routes.py`

**Interfaces:**
- Consumes: nothing from earlier tasks at runtime — it reads the columns
  Task 1 declared, by name. `FakeClient` (Task 3) in its tests.
- Produces, in `orchestrator.results_store`:
  - `ResultsStore` (ABC) with `latest_snapshot() -> dict | None`
  - `EmptyResultsStore()`
  - `SupabaseResultsStore(client)` and `SupabaseResultsStore.from_env()`
  - `RESULTS_TABLE: str` = `"aggregate_results"`

  Exported from `orchestrator` as `EmptyResultsStore`, `ResultsStore`,
  `SupabaseResultsStore`. Task 7 consumes `latest_snapshot()`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_results_routes.py`:

```python
"""
The read side of the aggregation snapshot, and the endpoint that serves it.

The store is checked against the fake Supabase client; the endpoint is
checked through a Flask test client with a store that returns whatever
the test wants. The case worth most here is the one a fresh checkout
hits: no snapshot at all.
"""
import pytest

from fakes import FakeClient
from orchestrator.results_store import (
    RESULTS_TABLE,
    EmptyResultsStore,
    SupabaseResultsStore,
)


def snapshot(id, generated_at, corpus_articles=1):
    return {"id": id, "run_id": id, "generated_at": generated_at,
            "articles_in_run": 1, "corpus_articles": corpus_articles,
            "payload": {"generated_at": generated_at, "corpus_articles": corpus_articles}}


# --- the store ---------------------------------------------------------
def test_the_empty_store_has_no_snapshot():
    assert EmptyResultsStore().latest_snapshot() is None


def test_the_supabase_store_returns_the_newest_snapshot():
    client = FakeClient(**{RESULTS_TABLE: [
        snapshot(1, "2026-09-28T12:00:00+00:00", corpus_articles=700),
        snapshot(2, "2026-09-29T12:00:00+00:00", corpus_articles=814),
    ]})

    latest = SupabaseResultsStore(client).latest_snapshot()

    assert latest is not None
    assert latest["corpus_articles"] == 814


def test_the_supabase_store_returns_none_for_an_empty_table():
    client = FakeClient(**{RESULTS_TABLE: []})
    assert SupabaseResultsStore(client).latest_snapshot() is None


def test_from_env_explains_what_is_missing(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        SupabaseResultsStore.from_env()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `python -m pytest tests/test_results_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator.results_store'`.

- [ ] **Step 3: Write the implementation**

Create `backend/orchestrator/results_store.py`:

```python
"""
The read side of the aggregation snapshot.

The aggregation agent writes aggregate_results through
agents/supabase_client.py; this is how the API reads it back. It lives in
orchestrator/ because orchestrator never imports an agent (see
docs/pipeline-coordinator.md, "Code layout") and the results endpoint is
an orchestrator concern — so, like SupabaseRunStore, it builds its own
client from os.environ rather than borrowing the agents' one.

Two implementations, matching store.py: Supabase when credentials are
set, and an empty store otherwise, so the app still starts for front-end
work without them.
"""
from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

RESULTS_TABLE = "aggregate_results"

# Every column of the table. The payload is the endpoint's answer; the
# rest is how the dashboard says which run produced it and when.
SELECT = "id, run_id, generated_at, articles_in_run, corpus_articles, payload"


class ResultsStore(ABC):
    @abstractmethod
    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """The most recently generated snapshot, or None if there is none."""


class EmptyResultsStore(ResultsStore):
    """
    Always no snapshot.

    Used when Supabase is not configured, so the app still starts for
    front-end work. The endpoint then answers with an empty payload and a
    reason — not with the invented figures the stub it replaces served.
    """

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        return None


class SupabaseResultsStore(ResultsStore):
    """
    Reads the newest row of aggregate_results.

    Takes a lock for the same reason SupabaseRunStore does: the client
    holds one HTTP connection, which cannot be shared across threads, and
    Flask serves requests on several.
    """

    def __init__(self, client: Any) -> None:
        self.client = client
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "SupabaseResultsStore":
        url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("Set SUPABASE_URL and SUPABASE_KEY to use SupabaseResultsStore")
        try:
            from supabase import create_client  # imported here so the app runs without it
        except ImportError as exc:
            raise RuntimeError(
                "SupabaseResultsStore needs the client library: pip install supabase"
            ) from exc
        return cls(create_client(url, key))

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            result = (
                self.client.table(RESULTS_TABLE)
                .select(SELECT)
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
        data = getattr(result, "data", None) or []
        return data[0] if data else None
```

- [ ] **Step 4: Export the new names**

In `backend/orchestrator/__init__.py`, add the import and the
`__all__` entries, keeping both lists alphabetical:

```python
from .results_store import EmptyResultsStore, ResultsStore, SupabaseResultsStore
```

```python
__all__ = [
    "AgentRegistry",
    "BackgroundRunner",
    "ContractError",
    "EmptyResultsStore",
    "InMemoryRunStore",
    "PipelineCoordinator",
    "ResultsStore",
    "RunAlreadyActive",
    "RunStore",
    "SupabaseResultsStore",
    "build_default_registry",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_results_routes.py -v`
Expected: PASS, 4 tests. Suite total: **132 tests**.

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/results_store.py backend/orchestrator/__init__.py \
        backend/tests/test_results_routes.py
git commit -m "Add the store that reads the newest aggregation snapshot"
```

---

### Task 7: `/api/v1/results` serves the snapshot

This task owns the second half of Review Focus item 5.

**Files:**
- Create: `backend/orchestrator/results_routes.py`
- Modify: `backend/app.py:82-125` (delete the stub `get_results()`, add
  `build_results_store()`, register the blueprint, update the module
  docstring at lines 1-14)
- Test: `backend/tests/test_results_routes.py` (append)

**Interfaces:**
- Consumes: `ResultsStore.latest_snapshot()` (Task 6);
  `compute.build_payload` keys (Task 2), for the sync test only.
- Produces: `orchestrator.results_routes.create_results_blueprint(store) -> Blueprint`
  at `/api/v1/results`, and `EMPTY_RESULTS: dict`. `app.build_results_store()`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_results_routes.py`:

```python
# --- the endpoint ------------------------------------------------------
from orchestrator.results_routes import EMPTY_RESULTS, create_results_blueprint  # noqa: E402
from orchestrator.results_store import ResultsStore                              # noqa: E402


class FixedStore(ResultsStore):
    def __init__(self, value=None):
        self.value = value

    def latest_snapshot(self):
        return self.value


def client_for(store):
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(create_results_blueprint(store))
    app.testing = True
    return app.test_client()


def test_the_endpoint_serves_the_stored_payload():
    stored = snapshot(3, "2026-09-29T12:00:00+00:00", corpus_articles=814)
    response = client_for(FixedStore(stored)).get("/api/v1/results")

    assert response.status_code == 200
    assert response.json["corpus_articles"] == 814
    assert response.json["snapshot_id"] == 3


def test_no_snapshot_yet_is_an_empty_payload_not_an_error():
    """
    A fresh database, or one where no run has reached aggregation. The
    dashboard should say 'nothing yet, start a run' from the same code
    path it renders real data with — not show 'Error: 503'.
    """
    response = client_for(FixedStore(None)).get("/api/v1/results")

    assert response.status_code == 200
    assert response.json["corpus_articles"] == 0
    assert response.json["snapshot_id"] is None
    assert response.json["sentiment_distribution"]["available"] is False
    assert response.json["top_topics"]["available"] is False
    assert response.json["articles"] == []
    assert "run" in response.json["reason"].lower()


def test_the_empty_payload_has_the_shape_the_agent_produces():
    """
    results_routes.py spells out the empty payload rather than importing
    the agent, because orchestrator never imports an agent. This is what
    keeps the two from drifting: one shape, one front end.
    """
    from agents.aggregation import compute

    real = compute.build_payload(
        generated_at="x", run_id=1, articles=[], classification_rows=[],
        topic_rows=[], sentiment_rows=[],
    )
    extra = {"snapshot_id", "reason"}

    assert set(EMPTY_RESULTS) - extra == set(real)
    assert set(EMPTY_RESULTS["sentiment_distribution"]) == set(real["sentiment_distribution"])
    assert set(EMPTY_RESULTS["top_topics"]) == set(real["top_topics"])


def test_the_app_serves_results_and_health_together():
    """The blueprint must not shadow the routes app.py already registers."""
    from app import create_app

    app = create_app()
    app.testing = True
    app_client = app.test_client()

    assert app_client.get("/api/v1/health").status_code == 200
    assert app_client.get("/api/v1/results").status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `python -m pytest tests/test_results_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'orchestrator.results_routes'`.

- [ ] **Step 3: Write the blueprint**

Create `backend/orchestrator/results_routes.py`:

```python
"""
The aggregated results endpoint.

  GET /api/v1/results   the newest aggregation snapshot

This replaces the hardcoded payload app.py used to serve. The shape is
the same one the front end was built against, plus the metadata that
says where the figures came from: generated_at, run_id, corpus_articles,
and an `available` flag per facet.

With no snapshot yet the answer is 200 and EMPTY_RESULTS, not an error
status: the dashboard renders 'nothing yet, start a run' through the same
code path it renders real data with, and a fresh checkout does not open
on a red error line.

TODO: accept filter query params (date range, source, topic) once
FilterPanel exists. A frozen snapshot cannot answer a filtered query —
see the open question in docs/pipeline-coordinator.md.
TODO(auth): the design doc puts results behind login (SS-5).
"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify

from .results_store import ResultsStore

# What the endpoint answers before any run has aggregated anything.
#
# Spelled out here rather than imported from the agent, because
# orchestrator never imports an agent (docs/pipeline-coordinator.md,
# "Code layout"). tests/test_results_routes.py fails if this and
# agents/aggregation/compute.build_payload drift apart.
EMPTY_RESULTS: Dict[str, Any] = {
    "snapshot_id": None,
    "reason": "No aggregation snapshot yet. Start a pipeline run — the "
              "aggregation stage writes one at the end of each run.",
    "generated_at": None,
    "run_id": None,
    "corpus_articles": 0,
    "articles_in_run": 0,
    "classified_articles": 0,
    "sentiment_distribution": {
        "available": False,
        "reason": "No aggregation snapshot yet.",
        "counted": 0,
        "other": 0,
        "positive": None,
        "neutral": None,
        "negative": None,
    },
    "top_topics": {
        "available": False,
        "reason": "No aggregation snapshot yet.",
        "counted": 0,
        "items": [],
    },
    "articles": [],
}


def create_results_blueprint(store: ResultsStore) -> Blueprint:
    bp = Blueprint("results", __name__, url_prefix="/api/v1/results")

    @bp.get("")
    def get_results():
        snapshot = store.latest_snapshot()
        if snapshot is None:
            return jsonify(dict(EMPTY_RESULTS))

        payload = dict(snapshot["payload"])
        payload["snapshot_id"] = snapshot["id"]
        payload["reason"] = None
        return jsonify(payload)

    return bp
```

- [ ] **Step 4: Wire it into the app**

In `backend/app.py`, add the imports:

```python
from orchestrator import (
    BackgroundRunner,
    EmptyResultsStore,
    InMemoryRunStore,
    PipelineCoordinator,
    build_default_registry,
)
from orchestrator.results_routes import create_results_blueprint
from orchestrator.results_store import SupabaseResultsStore
from orchestrator.routes import create_runs_blueprint
from orchestrator.supabase_store import SupabaseRunStore
```

add `build_results_store()` next to `build_run_store()`:

```python
def build_results_store():
    """
    Supabase when SUPABASE_URL / SUPABASE_KEY are set, empty otherwise.

    Same reasoning as build_run_store(): a missing variable should not be
    a hard startup failure, because front-end work needs the app to
    start without credentials. With no store the results endpoint answers
    'no snapshot yet' rather than serving figures nothing produced.
    """
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY")):
        logger.warning(
            "Supabase is not configured - /api/v1/results will report no snapshot"
        )
        return EmptyResultsStore()
    logger.info("Using SupabaseResultsStore for aggregated results")
    return SupabaseResultsStore.from_env()
```

register the blueprint in `create_app`, just after the runs blueprint:

```python
    app.register_blueprint(create_runs_blueprint(runner))
    app.register_blueprint(create_results_blueprint(build_results_store()))
```

and **delete the whole stub `get_results()` function**, from its
`@app.get("/api/v1/results")` decorator to its closing `})`.

Then correct the module docstring at the top of `app.py`:

```python
"""
ClassroomScope API Gateway (SS-4) — entry point.

STATUS:
  * /api/v1/runs    — pipeline coordinator endpoints. Collection,
                      security, classification and aggregation are real
                      agents; sentiment, topic and stance are stubs.
  * /api/v1/results — the newest aggregation snapshot. Computed from the
                      corpus, with a per-facet `available` flag: the
                      sentiment facet reports unavailable until a
                      sentiment agent exists.
  * Both stores are Supabase when SUPABASE_URL / SUPABASE_KEY are set,
    and fall back so the app still starts without credentials — see
    build_run_store() and build_results_store() below.
  * Auth is NOT connected yet — see the TODOs and
    docs/pipeline-coordinator.md.
"""
```

- [ ] **Step 5: Run the tests to verify they pass**

Run from `backend/`: `python -m pytest tests/test_results_routes.py -v`
Expected: PASS, 8 tests. Suite total: **136 tests**.

Run from `backend/`: `python -m pytest tests -q`
Expected: 136 passed.

- [ ] **Step 6: See the endpoint answer**

Run from `backend/`: `python app.py`, then in another terminal:

```bash
curl -s http://localhost:5000/api/v1/results | python -m json.tool | head -30
```

Expected: the snapshot Task 5 Step 7 wrote — `corpus_articles` in the
hundreds, `top_topics.available: true`, and
`sentiment_distribution.available: false` with a reason naming
`sentiment_results`.

- [ ] **Step 7: Type check**

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

- [ ] **Step 8: Commit**

```bash
git add backend/orchestrator/results_routes.py backend/app.py \
        backend/tests/test_results_routes.py
git commit -m "Serve the aggregation snapshot from /api/v1/results"
```

---

### Task 8: The dashboard renders real aggregates

**Files:**
- Modify: `frontend/src/components/DashboardShell.jsx` (the results
  sections and `PlaceholderNote`)
- Modify: `frontend/src/state/ViewStateContext.jsx` (refresh results when
  a run finishes; the poller's `isFinished` branch)
- Modify: `frontend/src/api/apiClient.js:8-14` (the `getResults()`
  status note)

**Interfaces:**
- Consumes: the payload from Task 7 — `generated_at`, `run_id`,
  `corpus_articles`, `articles_in_run`, `classified_articles`, `reason`,
  `sentiment_distribution.{available,reason,positive,neutral,negative,counted}`,
  `top_topics.{available,reason,items,counted}`,
  `articles[].{id,title,source,url,stakeholder,topic,sentiment}`.
- Produces: no new exports. `ViewStateContext` keeps its existing value
  shape, so `AdminConsole` and any other consumer are untouched.

There is no front-end test runner in this repo (`frontend/` has no test
script), so this task is verified by reading the rendered page. That is
the same standard the existing components were built to.

- [ ] **Step 1: Render the facets, and say when one is missing**

In `frontend/src/components/DashboardShell.jsx`, replace the module
docstring and the two `results &&` sections. The new body:

```jsx
/**
 * Dashboard Shell — presentation layer (Section 3 of design doc).
 *
 * STATUS:
 *   - AdminConsole is built and backed by real data.
 *   - The results sections render the aggregation snapshot: real topic
 *     and stakeholder figures computed from the corpus. Each facet
 *     carries an `available` flag, and a facet with no data says so
 *     instead of showing a number nothing produced — sentiment, until a
 *     sentiment agent exists.
 *
 * NOT built yet: FilterPanel, VisualizationViews (real charts),
 * ExportControls. See design doc Section 2 for what each needs to do.
 */
import { useEffect } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";

export default function DashboardShell() {
  const { results, loading, error, loadResults } = useViewState();

  useEffect(() => {
    loadResults();
  }, [loadResults]);

  return (
    <div style={{ fontFamily: "Arial, sans-serif", padding: "24px" }}>
      <header style={{ background: "#1F4E79", color: "#fff", padding: "14px 20px", borderRadius: "4px" }}>
        <strong>ClassroomScope</strong>
        <span style={{ marginLeft: "16px", fontSize: "13px", opacity: 0.8 }}>
          (in progress — no filters or login yet)
        </span>
      </header>

      <main style={{ marginTop: "20px" }}>
        {loading && <p>Loading results…</p>}
        {error && <p style={{ color: "#B85450" }}>Error: {error}</p>}

        {results && (
          <>
            <Provenance results={results} />

            <section>
              <h3 style={{ marginBottom: "4px" }}>Sentiment toward GAI in education</h3>
              {results.sentiment_distribution.available ? (
                <ul>
                  <li>Positive: {share(results.sentiment_distribution.positive)}</li>
                  <li>Neutral: {share(results.sentiment_distribution.neutral)}</li>
                  <li>Negative: {share(results.sentiment_distribution.negative)}</li>
                  <li style={{ color: "#666" }}>
                    from {results.sentiment_distribution.counted} analysed article(s)
                  </li>
                </ul>
              ) : (
                <MissingNote>{results.sentiment_distribution.reason}</MissingNote>
              )}
              {/* TODO: replace this list with the real donut chart component */}
            </section>

            <section style={{ marginTop: "20px" }}>
              <h3 style={{ marginBottom: "4px" }}>Top topics</h3>
              {results.top_topics.available ? (
                <ul>
                  {results.top_topics.items.map((t) => (
                    <li key={t.label}>
                      {t.label} — {t.count}
                    </li>
                  ))}
                </ul>
              ) : (
                <MissingNote>{results.top_topics.reason}</MissingNote>
              )}
              {/* TODO: replace this list with the real bar chart component */}
            </section>

            <section style={{ marginTop: "20px" }}>
              <h3 style={{ marginBottom: "4px" }}>Articles</h3>
              {results.articles.length === 0 ? (
                <MissingNote>
                  {results.reason || "No analysed articles in the corpus yet."}
                </MissingNote>
              ) : (
                <>
                  <p style={{ fontSize: "12px", color: "#666", margin: "0 0 8px" }}>
                    Showing {results.articles.length} of {results.corpus_articles} analysed
                    article(s); {results.classified_articles} classified.
                  </p>
                  <table style={{ borderCollapse: "collapse", width: "100%" }}>
                    <thead>
                      <tr style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>
                        <th>Title</th><th>Source</th><th>Stakeholder</th>
                        <th>Topic</th><th>Sentiment</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.articles.map((a) => (
                        <tr key={a.id} style={{ borderBottom: "1px solid #eee" }}>
                          <td>{a.url ? <a href={a.url}>{a.title}</a> : a.title}</td>
                          <td>{a.source}</td>
                          <td>{a.stakeholder ?? <NotYet />}</td>
                          <td>{a.topic ?? <NotYet />}</td>
                          <td>{a.sentiment ?? <NotYet />}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </section>
          </>
        )}

        <AdminConsole />
      </main>
    </div>
  );
}

/** A fraction from the API as a whole percentage. */
function share(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(0)}%` : "—";
}

/** Where these figures came from, so nobody has to guess how stale they are. */
function Provenance({ results }) {
  if (!results.generated_at) return null;
  return (
    <p style={{ fontSize: "12px", color: "#666", margin: "0 0 14px" }}>
      Aggregated {new Date(results.generated_at).toLocaleString()}
      {results.run_id != null && ` from run #${results.run_id}`}
      {results.articles_in_run > 0 &&
        `, which added ${results.articles_in_run} article(s)`}
      .
    </p>
  );
}

/** Marks a facet the pipeline cannot fill yet, with the reason it gave. */
function MissingNote({ children }) {
  return (
    <p
      style={{
        fontSize: "12px",
        color: "#8A5A00",
        background: "#FDF1DC",
        border: "1px solid #F0D9A8",
        borderRadius: "3px",
        padding: "6px 10px",
        margin: "0 0 10px",
        maxWidth: "70ch",
      }}
    >
      {children}
    </p>
  );
}

/** One cell no agent has filled in yet. */
function NotYet() {
  return <span style={{ color: "#999" }}>—</span>;
}
```

Note what this deletes: the old `PlaceholderNote` component and both of
its uses. Those notes existed to say the figures were invented. They are
not, now, so the notes would be wrong — and the honest version of each
is what `MissingNote` renders from the API's own `reason`.

- [ ] **Step 2: Refresh the results when a run finishes**

In `frontend/src/state/ViewStateContext.jsx`, inside the poller's
`isFinished(run)` branch, add the results refresh:

```jsx
      setSelectedRun(run);
      if (isFinished(run)) {
        watchedRunId.current = null;
        setActiveRunId(null);
        loadRuns();     // refresh the list so the finished run shows its outcome
        loadResults();  // the run just wrote a new snapshot; show it
      }
```

and add `loadResults` to that effect's dependency array:

```jsx
  }, [loadRuns, loadResults]);
```

`loadResults` is already a `useCallback` with an empty dependency list,
so it is stable and this does not rebuild the interval on every render.

Then correct the STATUS comment at the top of the file:

```jsx
 * STATUS:
 *   - results: real. /results serves the newest aggregation snapshot,
 *     with a per-facet `available` flag for what no agent produces yet.
 *   - run status + the run-status poller: real, reading pipeline_runs.
 *   - Does NOT yet hold active filters (TODO, needs FilterPanel).
```

- [ ] **Step 3: Correct the data-access-layer note**

In `frontend/src/api/apiClient.js`, replace the first STATUS bullet:

```js
 * STATUS:
 *   - getResults() returns the newest aggregation snapshot, computed from
 *     the corpus. Facets no agent fills yet carry available: false and a
 *     reason — read those rather than the numbers beside them.
 *   - The run endpoints below are real: they read pipeline_runs and
 *     pipeline_stage_runs, and return genuine rows.
 *   - Auth token attachment, retries, and export calls are NOT built yet.
```

- [ ] **Step 4: Verify the page**

With `python app.py` running in `backend/`, run from `frontend/`:
`npm run dev`, and open `http://localhost:5173`.

Expected:
- A provenance line naming the run and when it aggregated.
- **Top topics**: a real ranked list, no `-1_…` entry.
- **Articles**: real titles from the corpus, with a "Showing N of M" line
  and `—` in the Sentiment column.
- **Sentiment**: the amber note, reading `sentiment_results is not in the
  schema yet` (or `has no rows yet`) — not `0%`.
- No console errors.

Then click **Start a run** in the admin console and confirm the results
sections refresh by themselves when the run reaches a terminal status.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DashboardShell.jsx \
        frontend/src/state/ViewStateContext.jsx \
        frontend/src/api/apiClient.js
git commit -m "Render the real aggregates and name what is still missing"
```

---

### Task 9: Verify end to end and record it

The repo's documentation states what has been verified against the live
database, with the numbers. This task produces those numbers and writes
them down.

**Files:**
- Modify: `docs/pipeline-coordinator.md` (status block, "Which agents are
  real", "Code layout", the aggregation failure rule, "Testing plan",
  "Known limitations", "Open questions")
- Modify: `README.md` (status, "What's working right now", "What's NOT
  built yet", the pipeline-coordinator section, the test count)

**Interfaces:**
- Consumes: everything. Produces: no code.

- [ ] **Step 1: Run the full suite and the type checker**

Run from `backend/`: `python -m pytest tests -q`
Expected: 136 passed.

Run from the repo root: `python -m pyright backend/`
Expected: 0 errors.

If either fails, stop and fix it here — the docs are about to claim both.

- [ ] **Step 2: Run the pipeline against the real database**

With `backend/.env` holding the **secret** key, run from `backend/`:

```bash
python app.py
```

and in another terminal:

```bash
curl -X POST http://localhost:5000/api/v1/runs
# wait for it to finish, then:
curl -s http://localhost:5000/api/v1/runs | python -m json.tool | head -20
curl -s http://localhost:5000/api/v1/results | python -m json.tool > /tmp/results.json
```

Record, for the docs: the run number, its final status, the corpus size
(`corpus_articles`), `articles_in_run`, `classified_articles`, how many
topics came back, and which tables reported unavailable. Confirm the
`aggregate_results` row exists:

```sql
select id, run_id, corpus_articles, articles_in_run, generated_at
  from public.aggregate_results order by id desc limit 3;
```

- [ ] **Step 3: Update `docs/pipeline-coordinator.md`**

Make these edits, using the numbers from Step 2:

1. **The status block at the top** — change "three real agents" to
   "four real agents", update the test count to 136, and add a sentence
   to the verification paragraph naming the aggregation snapshot the run
   wrote and the corpus size it covered.
2. **"Which agents are real"** — change the Aggregation row from
   `stub | not written yet` to
   `**real** | agents/aggregation/ — aggregates the corpus into the /api/v1/results payload`.
3. **"Code layout"** — add under `orchestrator/`:
   `results_store.py   reads the newest aggregate_results row` and
   `results_routes.py  the /api/v1/results endpoint`; add under
   `agents/`: `aggregation/  corpus aggregation -> the dashboard payload`.
4. **Add a section, "Aggregation"**, after "Classification", modelled on
   the ones above it. It must say: that the stage reads the whole
   analysable corpus rather than `ctx.approved_ids`, and why; that the
   snapshot is one JSONB row per run, inserted not upserted; that
   `run_id` has no foreign key and why (`run_pipeline.py` keeps runs in
   memory); that a facet whose table is absent or empty is reported
   `available: false` rather than as zeros, and that sentiment is that
   facet today; and that aggregation expects
   `sentiment_results(article_id, sentiment_label)` with values
   `positive` / `neutral` / `negative` — the contract the sentiment owner
   needs to meet.
5. **"Testing plan"** — 136 tests, and mark the "have the dashboard poll
   run status" row's sibling: add a row
   `| aggregate the corpus | the aggregation rules, paging past 1000 rows, a table that is not in the schema | **landed** |`.
6. **"Known limitations and next steps"** — change "Four stages are still
   stubs" to "Three stages are still stubs" and drop aggregation from the
   list. Add: **a snapshot cannot answer a filtered query**, so
   FilterPanel needs either per-request aggregation or a normalised
   schema; and **`aggregate_results` grows by one row per run** with
   nothing pruning it.
7. **"Open questions for the team"** — add the five design decisions from
   this plan as questions 7-11, each in the same form as the existing
   ones: what was assumed, and what changes if the team decides
   otherwise.

- [ ] **Step 4: Update `README.md`**

1. **Status line and "What's working right now"** — `/api/v1/results` is
   no longer a stub: say it serves the newest aggregation snapshot, with
   real topic and stakeholder figures and an explicit unavailable marker
   for sentiment.
2. **"What's NOT built yet"** — remove the "Real data — everything above
   is served from a hardcoded stub" bullet. Replace it with a bullet
   saying sentiment and stance have no agent, so those columns are empty
   by design rather than broken.
3. **Pipeline coordinator section** — "Three of the seven agents are
   real" becomes "Four of the seven agents are real", and the list of
   what has no implementation drops aggregation.
4. **Test count** — `python -m pytest tests` runs **136 tests**, in both
   places the README states a count.
5. **"This week: initial site design refinement"** — the
   `VisualizationViews` item now has real data behind it: note that
   `top_topics.items` and the article table are live, and that whoever
   builds the charts should read each facet's `available` flag rather
   than the numbers beside it.

- [ ] **Step 5: Check the docs against the code**

Run from `backend/`: `python -m pytest tests -q` one more time
(the schema-sync test reads `docs/pipeline_tables.sql`, which Task 1
changed).
Expected: 136 passed.

Re-read every number written in Steps 3 and 4 against the output
captured in Step 2. A count in the docs that no command produces is the
thing this step exists to catch.

- [ ] **Step 6: Commit**

```bash
git add docs/pipeline-coordinator.md README.md
git commit -m "Record the aggregation agent and its end-to-end verification"
```

---

## Self-Review

Run after writing the plan, against the spec sources named in the header.

**1. Spec coverage.** The agent contract's eight rules for agent owners:
code in `agents/aggregation/` (Task 2, 4), an `Agent` subclass in
`adapters.py` (Task 5), `ctx` used for `run_id` / `approved_ids` /
`completed_analysis` and no article text (Task 5), reads and writes
through `get_client()` with no import-time `load_dotenv` (Task 4), own
table plus a summary dict (Tasks 1, 4, 5), raises on failure (Task 4
Step 1, `test_an_error_that_is_not_a_missing_table_is_raised`; Task 5,
`test_the_agent_raises_rather_than_reporting_an_empty_success`),
registered in `build_default_registry` (Task 5), and rule 8 — stay inside
the IDs you were given — knowingly departed from, with the reasoning in
Design Decision 1 and recorded as an open question in Task 9.

The output contract (`app.py`'s stub payload): `sentiment_distribution`,
`top_topics` and `articles` all survive as keys. `top_topics` changes
from a bare list to `{available, reason, counted, items}` — safe, because
`DashboardShell` never read it; `articles` keeps `id`, `title`, `source`,
`stakeholder`, `sentiment` and gains `url`, `topic`, `source_type`,
`published_date`. The coordinator's aggregation contract ("any dict") is
met. The aggregation failure rule (2 attempts, then
`completed_with_errors` with analysis results kept) needs no change and
is left alone.

**Gap found and closed:** the stub payload is the only written statement
of the output shape, and it has no provenance fields — so a reader could
not tell a fresh snapshot from a month-old one. Added `generated_at`,
`run_id`, `articles_in_run`, `classified_articles` and `snapshot_id`,
and the `Provenance` line in Task 8 renders them.

**Gap deliberately left open:** filters. `apiClient.getResults()` and the
`app.py` stub both carry a TODO for date-range / source / topic query
params. A frozen snapshot cannot answer those, so Task 7 keeps the TODO,
Design Decision 3 states the cost, and Task 9 Step 3.6 records it as a
limitation. Building it now would mean either a normalised schema or
per-request aggregation, for a UI that does not exist.

**2. Placeholder scan.** No "TBD", no "add error handling", no "similar
to Task N", no "write tests for the above". Every code step carries the
code. Task 8 has no test code because `frontend/` has no test runner —
stated in the task rather than implied, with a read-the-page verification
in its place. Task 9's doc edits are specified as numbered content
requirements rather than finished prose, because they must carry numbers
that only Step 2 produces; the numbers to capture are listed there.

**3. Type consistency.** Checked across tasks: `AGGREGATE_TABLE` /
`AGGREGATE_COLUMNS` (Task 1) are read by Task 4's code and Task 1's test;
`read_corpus()`'s five keys (Task 4) are exactly what Task 5 unpacks;
`build_payload`'s eight keys (Task 2) are what Task 7's `EMPTY_RESULTS`
mirrors and Task 8 renders; `latest_snapshot()` (Task 6) returns the row
whose `payload` and `id` Task 7 reads; `sentiment_label` is the column
name in Task 2's tests, Task 4's select, and Task 9's stated contract for
the sentiment owner. `BASELINE_CLASSIFIER = "baseline_keyword"` matches
what `adapters.ClassificationAgent._baseline` writes, and
`"gpt-5.6-luna"` in the tests matches `classify_luna.CLASSIFIER_TAG`.

**One inconsistency found and fixed:** Task 3's `fake_client` fixture was
first written to patch `agents.adapters.get_client` only, but the
aggregation adapter reads through `agents.aggregation.db.get_client` —
patching `adapters` would have left the real client in place and the
tests would have reached for credentials. The fixture takes a `module`
argument, and Task 5 adds the `agent_client` wrapper that passes `db`.

**A test that did not test what it claimed, found and fixed:** Task 4's
`test_an_error_that_is_not_a_missing_table_is_raised` first used a client
that raised on *every* table, so it exercised the `articles` read — which
has no tolerance at all — and never reached `read_optional`'s re-raise
branch, the one line it exists to pin. It now raises on
`sentiment_results` alone, leaving the other three readable. Task 5's
`test_the_agent_stores_a_snapshot_of_the_whole_corpus` also asserted
`stakeholder in ("Educator", None)`, which passes either way; the two
articles now carry different dates so the order is fixed and the
assertion is exact.

**Every cited line range was checked against the files** rather than
estimated: `test_agent_adapters.py:21-82`, `registry.py:85-114`,
`app.py:82-125`, `adapters.py` docstring 19-29,
`test_registry_wiring.py:25-26`, `apiClient.js:8-14`. So were the four
constants the plan's code depends on:
`classify_luna.CLASSIFIER_TAG == "gpt-5.6-luna"`, the baseline's
`"baseline_keyword"` tag, `SupabaseRunStore.from_env()`'s
`create_client(url, key)` pattern, and the articles columns collection
actually writes (`title`, `author`, `published_date`, `source`, `url`,
`content`, `content_hash`).

**4. Review Focus.** All five have a test in the owning task: the
1000-row cap → Task 4
`test_reads_past_the_thousand_row_response_limit` (2450 rows, three
pages); double-counted classifications → Task 2
`test_one_row_per_article_even_with_two_classifiers` and
`test_build_payload_does_not_double_count_a_twice_classified_article`;
the absent `sentiment_results` → Task 4
`test_a_missing_sentiment_table_is_reported_not_raised` and Task 5
`test_the_agent_succeeds_with_no_sentiment_table`, with
`test_a_missing_articles_table_is_not_tolerated` pinning the other side
of that line; BERTopic outliers and null topics → Task 2
`test_bertopic_outliers_are_not_a_topic`,
`test_null_and_blank_topics_are_skipped`,
`test_only_outlier_rows_reads_as_unavailable_not_as_an_empty_chart`; the
empty corpus → Task 2
`test_build_payload_over_an_empty_corpus_returns_a_payload_not_an_error`,
Task 5 `test_the_agent_stores_a_snapshot_for_an_empty_corpus`, and Task 7
`test_no_snapshot_yet_is_an_empty_payload_not_an_error`.
