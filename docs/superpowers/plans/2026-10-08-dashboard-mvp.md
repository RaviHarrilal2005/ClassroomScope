# Dashboard MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard list and filter the 328 real analysable articles, search articles and their 29,658 comments by keyword, and look demo-ready.

**Architecture:** A new backend module, `orchestrator/corpus.py`, reads the analysable articles plus their classification and topic rows (cached for 60s), filters them in Python per request, and serves them through `/api/v1/results` and a new `/api/v1/search/comments`. The React view-state store holds the filters and reloads on change; three new components render the filter panel, article table and comment results. A plain-CSS design system (`styles.css`) and a new two-tab layout restyle every view. Two workstreams run in parallel on separate branches: **A** (filters + search, backend and frontend logic) and **B** (redesign), joined by a coordinator merge.

**Tech Stack:** Python 3.13, Flask, supabase-py 2.31 (PostgREST), pytest; React 18, Vite 5, Recharts 3, plain CSS.

**Spec:** `docs/superpowers/specs/2026-10-08-dashboard-filters-redesign-design.md`

## Global Constraints

- No new npm or pip dependencies.
- No database writes, migrations, views or RPC functions. The new endpoints only read.
- Never click **Start a run** while the frontend points at `python app.py`: that runs the real agents and writes to the team's shared Supabase.
- `react-is` stays pinned to `^18` (it must match React's major; see the Recharts note in the spec's verification section).
- Ports: workstream A uses backend **5001** and Vite **5174**; workstream B uses backend **5002** and Vite **5175**. Never use 5000 or 5173 (the user's and another session's servers).
- Each workstream edits only the files the spec's "File ownership" table gives it.
- Comments match the codebase: a module docstring that says why, sparse inline comments, and `ponytail:` on a deliberate shortcut with a known ceiling.
- Commit messages are plain sentences in the repo's style (e.g. "Read the analysable corpus for the dashboard"), ending with:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- The frontend has no test runner. Frontend tasks verify with `npm run build` and a headless Edge render.
- Sentiment stays a placeholder: no task reads `sentiment_results`.

## Review Focus

1. **Fast successive filter changes** (typing a year into a date input fires several changes): only the newest response may reach the screen. Owned by Task A5 (request tickets); checked by hand in Task A6 step 6.
2. **Search terms containing LIKE or URL syntax** (`%`, `_`, `\`, quotes, commas, parentheses): match literally and never 500. `%`, `_` and `\` are pinned by Task A3's tests; quotes, commas and parentheses are checked against the real database in Task A6 step 6. `*` is a known PostgREST limitation (a wildcard), recorded in the README.
3. **Articles with no title, URL, date or source:** the table shows "Untitled" or "—" instead of crashing. Pinned in the backend by Task A2's `test_a_search_survives_missing_titles_and_text`; the frontend fallbacks are in Task A6's components.
4. **One table read failing** (e.g. `topic_results` times out): the whole dashboard shows the reason, not a 500, and recovers on the next request. Pinned by Task A1's `test_a_failed_read_is_reported_and_retried_next_time`.
5. **A 400 from the backend** (from after to, typed by hand): the error shows and the last good results stay on screen. Owned by Task A5; checked by hand in Task A6 step 6.

---

## Task 0 (coordinator): Groundwork both workstreams build on

Done by the coordinator on `dashboard-mvp` before either workstream starts.

**Files:**
- Create: `frontend/src/components/FilterPanel.jsx`, `frontend/src/components/ArticleTable.jsx`, `frontend/src/components/CommentResults.jsx` (stubs)
- Modify: `frontend/src/api/apiClient.js:18`, `frontend/src/state/ViewStateContext.jsx`, `frontend/src/components/DashboardShell.jsx:17,25-27`

**Interfaces:**
- Produces: `FilterPanel`, `ArticleTable`, `CommentResults` default exports, prop-less. `ViewStateProvider` loads results on mount (components no longer call `loadResults`). `BASE_URL` honours `VITE_API_URL`.

- [ ] **Step 1: Let the API base URL be set per dev server**

In `frontend/src/api/apiClient.js`, replace line 18:

```js
// VITE_API_URL lets two dev servers run side by side on other ports.
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:5000/api/v1";
```

- [ ] **Step 2: Move the initial results load into the provider**

In `frontend/src/state/ViewStateContext.jsx`, add after the `loadResults` `useCallback` (after line 67):

```js
  // The dashboard's results load once on mount. Workstream A replaces
  // this with an effect that reloads whenever the filters change.
  useEffect(() => {
    loadResults();
  }, [loadResults]);
```

In `frontend/src/components/DashboardShell.jsx`, delete `import { useEffect } from "react";` (line 17) and the mount effect (lines 25-27):

```js
  useEffect(() => {
    loadResults();
  }, [loadResults]);
```

and change line 23 to `const { results, loading, error } = useViewState();`.

- [ ] **Step 3: Commit the three component stubs**

`frontend/src/components/FilterPanel.jsx`:

```jsx
/** Filter panel. A stub until workstream A builds it (docs/superpowers/plans/2026-10-08-dashboard-mvp.md, Task A6). */
export default function FilterPanel() {
  return (
    <div className="filter-panel">
      <h2>Filters</h2>
      <p className="empty-note">Filters are on their way.</p>
    </div>
  );
}
```

`frontend/src/components/ArticleTable.jsx`:

```jsx
/** Article table. A stub until workstream A builds it (docs/superpowers/plans/2026-10-08-dashboard-mvp.md, Task A6). */
export default function ArticleTable() {
  return <p className="empty-note">The article table is on its way.</p>;
}
```

`frontend/src/components/CommentResults.jsx`:

```jsx
/** Comment search results. A stub until workstream A builds it (docs/superpowers/plans/2026-10-08-dashboard-mvp.md, Task A6). */
export default function CommentResults() {
  return null;
}
```

- [ ] **Step 4: Build and commit**

```bash
cd frontend && npm ci && npm run build
cd .. && git add frontend
git commit -m "Prepare the dashboard MVP: component stubs, configurable API URL

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

Expected: build succeeds.

- [ ] **Step 5: Bring Task 0 into each workstream's worktree**

The workstream branches and their worktrees already exist: they were created on 2026-10-08, before Task 0, to hold their README status notes. From the main checkout (`C:/Users/ravid/Projects/ClassroomScope`):

```bash
git -C ../ClassroomScope-mvp-filters merge --no-edit dashboard-mvp
git -C ../ClassroomScope-mvp-redesign merge --no-edit dashboard-mvp
cp backend/.env ../ClassroomScope-mvp-filters/backend/.env
cp backend/.env ../ClassroomScope-mvp-redesign/backend/.env
(cd ../ClassroomScope-mvp-filters/frontend && npm ci)
(cd ../ClassroomScope-mvp-redesign/frontend && npm ci)
```

`backend/.env` is git-ignored, so copying it commits nothing.

---

# Workstream A: filters and keyword search

Worktree: `C:/Users/ravid/Projects/ClassroomScope-mvp-filters`, branch `dashboard-mvp-filters`. Run Python from `backend/`. The baseline suite is **113 passed**.

## Task A1: Read the analysable corpus

**Files:**
- Create: `backend/orchestrator/corpus.py`
- Create: `backend/tests/fake_supabase.py`
- Test: `backend/tests/test_corpus.py`

**Interfaces:**
- Produces: `corpus.page_all(query: Callable[[], Any], page_size=1000) -> List[dict]`; `corpus.read_corpus(client) -> List[Article]` where each Article has `id, title, source, url, published_date, clean_content (str, never None), source_type, stakeholder, stable_topic_id, topic`; `corpus.unavailable(reason) -> Corpus`; `corpus.reader(client, ttl=60, clock=time.monotonic) -> Callable[[], Corpus]`. `Corpus = {"available": bool, "reason": str | None, "articles": [Article]}`. `fake_supabase.FakeSupabase(cap=1000, error=None, **tables)` with `.opened` and `.patterns`.

- [ ] **Step 1: Write the fake Supabase client**

`backend/tests/fake_supabase.py`:

```python
"""
An in-memory stand-in for the Supabase tables the dashboard reads.

Implements just the PostgREST calls orchestrator/corpus.py makes, with
the server's habit of capping each response at `cap` rows. Records every
table opened and every ilike pattern, so tests can check what was asked.
"""
import re
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, client, rows):
        self.client, self.rows, self.window, self.counting = client, list(rows), None, False

    def select(self, columns, count=None):
        self.counting = count == "exact"
        return self

    def eq(self, column, value):
        self.rows = [r for r in self.rows if r.get(column) == value]
        return self

    def in_(self, column, values):
        values = set(values)
        self.rows = [r for r in self.rows if r.get(column) in values]
        return self

    def ilike(self, column, pattern):
        self.client.patterns.append(pattern)
        assert pattern.startswith("%") and pattern.endswith("%"), pattern
        needle = re.sub(r"\\(.)", r"\1", pattern[1:-1]).lower()
        self.rows = [r for r in self.rows if needle in (r.get(column) or "").lower()]
        return self

    def order(self, column, desc=False):
        self.rows.sort(key=lambda r: r.get(column) or "", reverse=desc)
        return self

    def range(self, start, end):
        self.window = (start, min(end + 1, start + self.client.cap))
        return self

    def limit(self, size):
        self.window = (0, size)
        return self

    def execute(self):
        if self.client.error:
            raise self.client.error
        data = self.rows[slice(*self.window)] if self.window else self.rows
        return SimpleNamespace(data=data, count=len(self.rows) if self.counting else None)


class FakeSupabase:
    def __init__(self, cap=1000, error=None, **tables):
        self.tables, self.cap, self.error = tables, cap, error
        self.opened, self.patterns = [], []

    def table(self, name):
        self.opened.append(name)
        return FakeQuery(self, self.tables.get(name, []))
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_corpus.py`:

```python
"""
The dashboard's corpus: which articles count, what each one is labelled,
and how filters and search narrow them.

What goes wrong here is quiet: an irrelevant article counted, the keyword
baseline overriding the LLM's label, a capped page dropping rows, or a
`%` in a search matching everything.
"""
import pytest

from fake_supabase import FakeSupabase
from orchestrator import corpus


def article(id, title="An article", date="2026-09-01T10:00:00+00:00", content="Some text.",
            relevant=True, status="success", **extra):
    return {"id": id, "title": title, "source": "Example News", "url": f"https://example.com/{id}",
            "published_date": date, "clean_content": content, "llm_relevant": relevant,
            "processing_status": status, **extra}


def classified(article_id, classifier, stakeholder, source_type="blog", at="2026-09-18T00:00:00+00:00", id=None):
    return {"id": id or article_id * 10 + len(classifier), "article_id": article_id, "classifier": classifier,
            "stakeholder_category": stakeholder, "source_type": source_type, "classified_at": at}


def topic(article_id, stable_topic_id, label=None, id=None):
    return {"id": id or article_id, "article_id": article_id, "stable_topic_id": stable_topic_id, "topic": label}


def corpus_row(id, **fields):
    """A merged corpus article, as read_corpus returns it."""
    row = {"id": id, "title": f"Article {id}", "source": "Example News", "url": f"https://example.com/{id}",
           "published_date": "2026-09-01T10:00:00+00:00", "clean_content": "Some text.",
           "source_type": "blog", "stakeholder": "students", "stable_topic_id": None, "topic": None}
    row.update(fields)
    return row


NO_FILTERS = {key: "" for key in ("from", "to", "source_type", "stakeholder", "topic", "q")}


def filters(**set_values):
    return {**NO_FILTERS, **set_values}


# --- read_corpus ----------------------------------------------------------

def test_only_analysable_articles_are_read():
    client = FakeSupabase(articles=[
        article(1), article(2, relevant=False), article(3, status="failed"), article(4, relevant=None),
    ])
    assert [a["id"] for a in corpus.read_corpus(client)] == [1]


def test_a_real_classifier_beats_the_keyword_baseline_even_when_older():
    client = FakeSupabase(
        articles=[article(1), article(2)],
        classification_results=[
            classified(1, "gpt-5.6-luna", "educators", "news_outlet", at="2026-09-01T00:00:00+00:00"),
            classified(1, "baseline_keyword", "students", "blog", at="2026-10-01T00:00:00+00:00"),
            classified(2, "baseline_keyword", "parents", "academic"),
        ],
    )
    by_id = {a["id"]: a for a in corpus.read_corpus(client)}
    assert (by_id[1]["stakeholder"], by_id[1]["source_type"]) == ("educators", "news_outlet")
    # Baseline is still used when it is all there is.
    assert (by_id[2]["stakeholder"], by_id[2]["source_type"]) == ("parents", "academic")


def test_an_unclassified_article_has_no_labels():
    a = corpus.read_corpus(FakeSupabase(articles=[article(1)]))[0]
    assert (a["stakeholder"], a["source_type"], a["stable_topic_id"], a["topic"]) == (None, None, None, None)


def test_the_newest_topic_row_wins_and_no_stable_id_means_unassigned():
    client = FakeSupabase(
        articles=[article(1), article(2)],
        topic_results=[
            topic(1, "T001", "Old label", id=1),
            topic(1, "T004", "Integrity", id=9),
            topic(2, None, "Outliers", id=5),
        ],
    )
    by_id = {a["id"]: a for a in corpus.read_corpus(client)}
    assert (by_id[1]["stable_topic_id"], by_id[1]["topic"]) == ("T004", "Integrity")
    assert (by_id[2]["stable_topic_id"], by_id[2]["topic"]) == (None, None)


def test_every_page_is_read_even_when_the_server_caps_pages():
    client = FakeSupabase(cap=2, articles=[article(i) for i in range(1, 6)],
                          topic_results=[topic(i, "T001", "Adoption") for i in range(1, 6)])
    rows = corpus.read_corpus(client)
    assert len(rows) == 5
    assert all(r["stable_topic_id"] == "T001" for r in rows)


def test_missing_text_reads_as_empty():
    a = corpus.read_corpus(FakeSupabase(articles=[article(1, content=None)]))[0]
    assert a["clean_content"] == ""


# --- reader -----------------------------------------------------------------

def test_reader_caches_until_the_ttl_passes():
    now = [0.0]
    client = FakeSupabase(articles=[article(1)])
    read = corpus.reader(client, ttl=60, clock=lambda: now[0])

    assert read()["available"] is True
    opened = len(client.opened)
    now[0] = 59
    read()
    assert len(client.opened) == opened  # served from the cache
    now[0] = 61
    read()
    assert len(client.opened) == 2 * opened


def test_a_failed_read_is_reported_and_retried_next_time():
    client = FakeSupabase(articles=[article(1)], error=ConnectionError("network down"))
    read = corpus.reader(client, ttl=60, clock=lambda: 0.0)

    first = read()
    assert first == {"available": False, "reason": "Could not read the articles; see the backend log.",
                     "articles": []}
    client.error = None
    assert read()["available"] is True  # the failure was not cached
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: collection error, `ImportError: cannot import name 'corpus' from 'orchestrator'`.

- [ ] **Step 4: Write the reading half of the module**

`backend/orchestrator/corpus.py` (later tasks append below the reading section; the imports they need are already here):

```python
"""
The analysable corpus for the dashboard: each article with one source
type, stakeholder and topic, filtered and searched per request.

MVP (README, "MVP features — come back to these"): this reads four
tables and filters in Python, behind a 60-second cache. Fine at a few
hundred articles. The aggregation snapshot, or a Postgres view, should
replace it once the corpus grows or the numbers must match a run.

Merge rules, one value per article:
  * classification: any classifier beats `baseline_keyword`; ties go to
    the newest `classified_at`.
  * topic: the newest topic_results row. No row, or no stable topic ID,
    means unassigned.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .topic_counts import top_topics
from .topic_counts import unavailable as topics_unavailable

logger = logging.getLogger(__name__)

Article = Dict[str, Any]
Corpus = Dict[str, Any]  # {"available": bool, "reason": str | None, "articles": [Article]}
CommentSearch = Callable[[List[Article], str], Dict[str, Any]]

FILTER_KEYS = ("from", "to", "source_type", "stakeholder", "topic", "q")
# Exact-match filters: query param -> article field.
EXACT_FILTERS = {"source_type": "source_type", "stakeholder": "stakeholder", "topic": "stable_topic_id"}
# What /results sends per article. clean_content stays on the server.
ARTICLE_FIELDS = ("id", "title", "url", "source", "published_date", "source_type",
                  "stakeholder", "stable_topic_id", "topic", "snippet")
BASELINE_CLASSIFIER = "baseline_keyword"
SNIPPET_CONTEXT = 80
CACHE_SECONDS = 60
COMMENT_LIMIT = 50
NOT_CONFIGURED = "Supabase is not configured, so there are no articles to read."


# --- reading ---------------------------------------------------------------

def page_all(query: Callable[[], Any], page_size: int = 1000) -> List[Dict[str, Any]]:
    """
    Every row a query matches. `query` builds a fresh query on each call.

    PostgREST returns at most its max-rows per request whatever range is
    asked for, so this pages until a page comes back empty rather than
    trusting a short page to be the last.
    """
    rows: List[Dict[str, Any]] = []
    while True:
        page = query().range(len(rows), len(rows) + page_size - 1).execute().data
        if not page:
            return rows
        rows.extend(page)


def _classifier_rank(row: Mapping[str, Any]) -> Tuple[bool, str]:
    return (row.get("classifier") != BASELINE_CLASSIFIER, row.get("classified_at") or "")


def read_corpus(client: Any) -> List[Article]:
    """The analysable articles, each with source_type, stakeholder, stable_topic_id and topic."""
    articles = page_all(lambda: client.table("articles")
                        .select("id, title, source, url, published_date, clean_content")
                        .eq("llm_relevant", True).eq("processing_status", "success").order("id"))
    classifications = page_all(lambda: client.table("classification_results")
                               .select("article_id, classifier, stakeholder_category, source_type, classified_at")
                               .order("id"))
    topic_rows = page_all(lambda: client.table("topic_results")
                          .select("article_id, stable_topic_id, topic").order("id"))

    best: Dict[Any, Mapping[str, Any]] = {}
    for row in classifications:
        current = best.get(row["article_id"])
        if current is None or _classifier_rank(row) > _classifier_rank(current):
            best[row["article_id"]] = row
    newest_topic = {row["article_id"]: row for row in topic_rows}  # ordered by id, so the last wins

    corpus = []
    for article in articles:
        label = best.get(article["id"], {})
        topic = newest_topic.get(article["id"], {})
        topic_id = topic.get("stable_topic_id")
        corpus.append({
            **article,
            "clean_content": article.get("clean_content") or "",
            "source_type": label.get("source_type"),
            "stakeholder": label.get("stakeholder_category"),
            "stable_topic_id": topic_id,
            "topic": (topic.get("topic") or topic_id) if topic_id else None,
        })
    return corpus


def unavailable(reason: str) -> Corpus:
    return {"available": False, "reason": reason, "articles": []}


def reader(client: Any, ttl: float = CACHE_SECONDS,
           clock: Callable[[], float] = time.monotonic) -> Callable[[], Corpus]:
    """
    The corpus, re-read at most every `ttl` seconds.

    A failed read becomes an unavailable corpus rather than a 500, and is
    not cached, so the next request tries again.
    """
    # ponytail: one cache per process and no lock; two requests at expiry may both re-read.
    cache: Dict[str, Any] = {"at": None, "corpus": None}

    def read() -> Corpus:
        if cache["at"] is not None and clock() - cache["at"] < ttl:
            return cache["corpus"]
        try:
            corpus = {"available": True, "reason": None, "articles": read_corpus(client)}
        except Exception:
            logger.exception("Could not read the article corpus")
            return unavailable("Could not read the articles; see the backend log.")
        cache.update(at=clock(), corpus=corpus)
        return corpus

    return read
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: `8 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/orchestrator/corpus.py backend/tests/fake_supabase.py backend/tests/test_corpus.py
git commit -m "Read the analysable corpus for the dashboard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task A2: Filter, search and summarise the corpus

**Files:**
- Modify: `backend/orchestrator/corpus.py` (append a filtering section)
- Test: `backend/tests/test_corpus.py` (append)

**Interfaces:**
- Consumes: `Article`, `Corpus`, `unavailable`, `FILTER_KEYS`, `EXACT_FILTERS`, `ARTICLE_FIELDS` from Task A1; `topic_counts.top_topics`.
- Produces: `corpus.parse_filters(args: Mapping) -> Dict[str, str]` (all six keys, trimmed; raises `ValueError(message)`); `corpus.make_snippet(text, q, context=80) -> Optional[str]`; `corpus.filter_articles(articles, filters) -> List[Article]` (each with `snippet`); `corpus.filter_options(articles) -> dict`; `corpus.results_payload(corpus, filters) -> {"top_topics", "articles", "filter_options"}` where `articles = {available, reason, total, corpus, items}`.

- [ ] **Step 1: Append the failing tests to `backend/tests/test_corpus.py`**

```python
# --- parse_filters --------------------------------------------------------

def test_filters_default_to_empty_and_are_trimmed():
    assert corpus.parse_filters({}) == NO_FILTERS
    assert corpus.parse_filters({"stakeholder": "  educators ", "q": " cheating "})["q"] == "cheating"


@pytest.mark.parametrize("args, message", [
    ({"from": "08/10/2026"}, "'from' must be a date"),
    ({"to": "2026-13-01"}, "'to' must be a date"),
    ({"from": "2026-10-02", "to": "2026-10-01"}, "'from' must not be after 'to'"),
    ({"q": "a"}, "2 to 100 characters"),
    ({"q": "x" * 101}, "2 to 100 characters"),
])
def test_bad_filters_are_rejected_with_a_reason(args, message):
    with pytest.raises(ValueError, match=message):
        corpus.parse_filters(args)


def test_dates_are_normalised_so_they_compare_as_text():
    assert corpus.parse_filters({"from": "2026-1-5"})["from"] == "2026-01-05"


# --- filter_articles --------------------------------------------------------

def test_date_range_is_inclusive_and_undated_articles_drop_out_only_when_dates_are_set():
    rows = [corpus_row(1, published_date="2026-09-01T23:59:00+00:00"),
            corpus_row(2, published_date="2026-09-02T00:00:00+00:00"),
            corpus_row(3, published_date=None)]
    assert [a["id"] for a in corpus.filter_articles(rows, filters(**{"from": "2026-09-01", "to": "2026-09-01"}))] == [1]
    assert [a["id"] for a in corpus.filter_articles(rows, filters(**{"from": "2026-09-02"}))] == [2]
    assert {a["id"] for a in corpus.filter_articles(rows, NO_FILTERS)} == {1, 2, 3}


def test_exact_filters_combine():
    rows = [corpus_row(1, source_type="blog", stakeholder="students", stable_topic_id="T001"),
            corpus_row(2, source_type="blog", stakeholder="educators", stable_topic_id="T001"),
            corpus_row(3, source_type="news_outlet", stakeholder="students", stable_topic_id="T001"),
            corpus_row(4, source_type="blog", stakeholder="students", stable_topic_id="T002")]
    got = corpus.filter_articles(rows, filters(source_type="blog", stakeholder="students", topic="T001"))
    assert [a["id"] for a in got] == [1]


def test_newest_first_and_undated_last():
    rows = [corpus_row(1, published_date=None),
            corpus_row(2, published_date="2026-01-01T00:00:00+00:00"),
            corpus_row(3, published_date="2026-06-01T00:00:00+00:00")]
    assert [a["id"] for a in corpus.filter_articles(rows, NO_FILTERS)] == [3, 2, 1]


def test_search_ignores_case_and_snips_around_the_first_match():
    text = "A" * 200 + " Students admit CHEATING with chatbots. " + "B" * 200
    rows = [corpus_row(1, clean_content=text), corpus_row(2, clean_content="Nothing relevant.")]
    got = corpus.filter_articles(rows, filters(q="cheating"))
    assert [a["id"] for a in got] == [1]
    snippet = got[0]["snippet"]
    assert "CHEATING" in snippet
    assert snippet.startswith("…") and snippet.endswith("…")
    assert len(snippet) < 200


def test_a_title_only_match_counts_but_has_no_snippet():
    got = corpus.filter_articles([corpus_row(1, title="Cheating scandal", clean_content="Nothing here.")],
                                 filters(q="cheating"))
    assert [(a["id"], a["snippet"]) for a in got] == [(1, None)]


def test_a_search_survives_missing_titles_and_text():
    rows = [corpus_row(1, title=None, clean_content="")]
    assert corpus.filter_articles(rows, filters(q="anything")) == []


def test_snippets_collapse_newlines_and_skip_ellipses_at_the_edges():
    assert corpus.make_snippet("Short\n\ntext about AI.", "ai") == "Short text about AI."
    assert corpus.make_snippet("no match here", "ai tutor") is None


# --- results_payload ------------------------------------------------------

def test_topics_are_counted_over_the_filtered_articles_only():
    rows = [corpus_row(1, stakeholder="students", stable_topic_id="T004", topic="Integrity"),
            corpus_row(2, stakeholder="students", stable_topic_id=None),
            corpus_row(3, stakeholder="educators", stable_topic_id="T001", topic="Adoption")]
    payload = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(stakeholder="students"))
    assert payload["top_topics"]["items"] == [{"label": "Integrity", "count": 1}]
    assert (payload["top_topics"]["counted"], payload["top_topics"]["unassigned"]) == (1, 1)
    assert (payload["articles"]["total"], payload["articles"]["corpus"]) == (2, 3)


def test_articles_go_out_without_their_text():
    rows = [corpus_row(1, clean_content="The whole article body.")]
    item = corpus.results_payload({"available": True, "reason": None, "articles": rows}, NO_FILTERS)["articles"]["items"][0]
    assert "clean_content" not in item
    assert set(item) == set(corpus.ARTICLE_FIELDS)


def test_filter_options_come_from_the_whole_corpus():
    rows = [corpus_row(1, source_type="blog", stakeholder="students", stable_topic_id="T004", topic="Integrity",
                       published_date="2026-02-01T00:00:00+00:00"),
            corpus_row(2, source_type="academic", stakeholder=None, stable_topic_id="T001", topic="Adoption",
                       published_date="2025-11-30T00:00:00+00:00")]
    options = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(source_type="blog"))["filter_options"]
    assert options == {
        "source_types": ["academic", "blog"],
        "stakeholders": ["students"],
        "topics": [{"id": "T001", "label": "Adoption"}, {"id": "T004", "label": "Integrity"}],
        "date_min": "2025-11-30",
        "date_max": "2026-02-01",
    }


def test_no_matches_says_so_instead_of_drawing_an_empty_chart():
    rows = [corpus_row(1, stakeholder="students")]
    payload = corpus.results_payload({"available": True, "reason": None, "articles": rows},
                                     filters(stakeholder="parents"))
    assert payload["top_topics"]["available"] is False
    assert payload["top_topics"]["reason"] == "No articles match these filters."
    assert payload["articles"]["items"] == []


def test_an_unavailable_corpus_gives_the_same_shape_with_a_reason():
    payload = corpus.results_payload(corpus.unavailable("Database down."), NO_FILTERS)
    assert payload["articles"] == {"available": False, "reason": "Database down.", "total": 0, "corpus": 0, "items": []}
    assert payload["top_topics"]["reason"] == "Database down."
    assert payload["filter_options"]["topics"] == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: the new tests fail with `AttributeError: module 'orchestrator.corpus' has no attribute 'parse_filters'` (and similar); the 8 from Task A1 still pass.

- [ ] **Step 3: Append the filtering section to `backend/orchestrator/corpus.py`**

```python
# --- filtering -------------------------------------------------------------

def parse_filters(args: Mapping[str, Any]) -> Dict[str, str]:
    """The filter query params, trimmed and checked. Raises ValueError with a message for the caller."""
    filters = {key: (args.get(key) or "").strip() for key in FILTER_KEYS}
    for key in ("from", "to"):
        if filters[key]:
            try:
                filters[key] = datetime.strptime(filters[key], "%Y-%m-%d").date().isoformat()
            except ValueError:
                raise ValueError(f"'{key}' must be a date like 2026-10-08.") from None
    if filters["from"] and filters["to"] and filters["from"] > filters["to"]:
        raise ValueError("'from' must not be after 'to'.")
    if filters["q"] and not 2 <= len(filters["q"]) <= 100:
        raise ValueError("Search terms must be 2 to 100 characters.")
    return filters


def make_snippet(text: str, q: str, context: int = SNIPPET_CONTEXT) -> Optional[str]:
    """About `context` characters either side of the first case-insensitive match of `q`, or None."""
    at = text.lower().find(q.lower())
    if at < 0:
        return None
    start, end = max(0, at - context), min(len(text), at + len(q) + context)
    body = " ".join(text[start:end].split())
    return ("…" if start > 0 else "") + body + ("…" if end < len(text) else "")


def _day(value: Optional[str]) -> Optional[str]:
    """The YYYY-MM-DD part of an ISO timestamp."""
    return value[:10] if value else None


def filter_articles(articles: Iterable[Article], filters: Mapping[str, str]) -> List[Article]:
    """
    The articles matching every set filter, newest first, undated last.

    `q` matches the title or the text, ignoring case. Each article comes
    back with a `snippet` from its text around the match: None when there
    is no `q`, or when only the title matched.
    """
    start, end, q = filters.get("from"), filters.get("to"), filters.get("q")
    matched = []
    for article in articles:
        if start or end:
            day = _day(article.get("published_date"))
            if day is None or (start and day < start) or (end and day > end):
                continue
        if any(filters.get(key) and article.get(field) != filters[key]
               for key, field in EXACT_FILTERS.items()):
            continue
        snippet = None
        if q:
            snippet = make_snippet(article.get("clean_content") or "", q)
            if snippet is None and q.lower() not in (article.get("title") or "").lower():
                continue
        matched.append({**article, "snippet": snippet})
    matched.sort(key=lambda a: a.get("published_date") or "", reverse=True)
    return matched


def filter_options(articles: List[Article]) -> Dict[str, Any]:
    """What the filter controls offer. Built from the whole corpus, so options don't vanish while filtering."""
    days = sorted(day for day in (_day(a.get("published_date")) for a in articles) if day)
    topics = {a["stable_topic_id"]: a["topic"] for a in articles if a.get("stable_topic_id")}
    return {
        "source_types": sorted({a["source_type"] for a in articles if a.get("source_type")}),
        "stakeholders": sorted({a["stakeholder"] for a in articles if a.get("stakeholder")}),
        "topics": sorted(({"id": i, "label": label} for i, label in topics.items()),
                         key=lambda t: t["label"]),
        "date_min": days[0] if days else None,
        "date_max": days[-1] if days else None,
    }


def results_payload(corpus: Corpus, filters: Mapping[str, str]) -> Dict[str, Any]:
    """The corpus-backed part of /results: top_topics, articles and filter_options."""
    if not corpus["available"]:
        return {
            "top_topics": topics_unavailable(corpus["reason"]),
            "articles": {"available": False, "reason": corpus["reason"], "total": 0, "corpus": 0, "items": []},
            "filter_options": filter_options([]),
        }
    everything = corpus["articles"]
    matched = filter_articles(everything, filters)
    if matched:
        topics = top_topics(matched)
    elif any(filters.values()):
        topics = topics_unavailable("No articles match these filters.")
    else:
        topics = topics_unavailable("There are no analysable articles yet.")
    return {
        "top_topics": topics,
        "articles": {
            "available": True,
            "reason": None,
            "total": len(matched),
            "corpus": len(everything),
            "items": [{field: article.get(field) for field in ARTICLE_FIELDS} for article in matched],
        },
        "filter_options": filter_options(everything),
    }
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: `27 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/corpus.py backend/tests/test_corpus.py
git commit -m "Filter and search the corpus, and recount topics over the result

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task A3: Search comments

**Files:**
- Modify: `backend/orchestrator/corpus.py` (append a comment-search section)
- Test: `backend/tests/test_corpus.py` (append)

**Interfaces:**
- Consumes: `make_snippet`, `unavailable`, `reader`, `NOT_CONFIGURED`, `COMMENT_LIMIT`, `CommentSearch` from Tasks A1–A2.
- Produces: `corpus.comments_unavailable(reason) -> {"available": False, "reason", "total": 0, "comments": []}`; `corpus.escape_like(text) -> str`; `corpus.search_comments(client, articles, q, limit=50) -> {"available", "reason", "total", "comments": [{comment_id, article_id, article_title, created_at, recommendation_count, snippet}]}`; `corpus.from_env() -> (read: Callable[[], Corpus], search: Callable[[List[Article], str], dict])`.

- [ ] **Step 1: Append the failing tests to `backend/tests/test_corpus.py`**

```python
# --- search_comments ------------------------------------------------------

def comment(comment_id, article_id, body, created="2026-09-01T00:00:00+00:00", recommends=0):
    return {"comment_id": comment_id, "article_id": article_id, "body_text": body,
            "created_at": created, "recommendation_count": recommends}


def test_comments_are_searched_only_on_the_given_articles_newest_first():
    client = FakeSupabase(comments=[
        comment("c1", 1, "Cheating is rampant", created="2026-09-01T00:00:00+00:00"),
        comment("c2", 1, "cheating again", created="2026-09-03T00:00:00+00:00", recommends=4),
        comment("c3", 2, "Cheating elsewhere"),
        comment("c4", 1, "Unrelated"),
    ])
    got = corpus.search_comments(client, [corpus_row(1, title="AI in class")], "CHEATING")
    assert got["total"] == 2
    assert [c["comment_id"] for c in got["comments"]] == ["c2", "c1"]
    assert got["comments"][0] == {"comment_id": "c2", "article_id": 1, "article_title": "AI in class",
                                  "created_at": "2026-09-03T00:00:00+00:00", "recommendation_count": 4,
                                  "snippet": "cheating again"}


def test_the_total_counts_every_match_but_only_the_limit_comes_back():
    client = FakeSupabase(comments=[comment(f"c{i}", 1, "chatbot") for i in range(60)])
    got = corpus.search_comments(client, [corpus_row(1)], "chatbot")
    assert (got["total"], len(got["comments"])) == (60, corpus.COMMENT_LIMIT)


@pytest.mark.parametrize("q, pattern", [
    ("50%", "%50\\%%"),
    ("snake_case", "%snake\\_case%"),
    ("back\\slash", "%back\\\\slash%"),
])
def test_like_wildcards_in_a_search_match_literally(q, pattern):
    client = FakeSupabase(comments=[comment("c1", 1, f"about {q} here"), comment("c2", 1, "something else")])
    got = corpus.search_comments(client, [corpus_row(1)], q)
    assert client.patterns == [pattern]
    assert [c["comment_id"] for c in got["comments"]] == ["c1"]


def test_no_articles_means_no_query():
    client = FakeSupabase(comments=[comment("c1", 1, "chatbot")])
    assert corpus.search_comments(client, [], "chatbot") == {"available": True, "reason": None, "total": 0, "comments": []}
    assert client.opened == []


def test_without_supabase_both_readers_say_why(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    read, search = corpus.from_env()
    assert read() == corpus.unavailable(corpus.NOT_CONFIGURED)
    assert search([corpus_row(1)], "chatbot")["reason"] == corpus.NOT_CONFIGURED
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: the new tests fail with `AttributeError: ... has no attribute 'search_comments'` / `'from_env'`; the earlier 27 pass.

- [ ] **Step 3: Append the comment-search section to `backend/orchestrator/corpus.py`**

```python
# --- comment search --------------------------------------------------------

def comments_unavailable(reason: str) -> Dict[str, Any]:
    return {"available": False, "reason": reason, "total": 0, "comments": []}


def escape_like(text: str) -> str:
    """`text` for a LIKE pattern, with its wildcards matched literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_comments(client: Any, articles: List[Article], q: str,
                    limit: int = COMMENT_LIMIT) -> Dict[str, Any]:
    """
    Comments on `articles` containing `q`, ignoring case, newest first.

    `total` counts every match; at most `limit` come back. PostgREST reads
    `*` in a pattern as a wildcard and has no escape for it, so a `*` in
    `q` matches anything.
    """
    if not articles:
        return {"available": True, "reason": None, "total": 0, "comments": []}
    titles = {a["id"]: a.get("title") for a in articles}
    # ponytail: the article IDs travel in the URL; past ~1,500 articles move this into an RPC.
    response = (client.table("comments")
                .select("comment_id, article_id, body_text, created_at, recommendation_count", count="exact")
                .in_("article_id", sorted(titles))
                .ilike("body_text", f"%{escape_like(q)}%")
                .order("created_at", desc=True)
                .limit(limit)
                .execute())
    return {
        "available": True,
        "reason": None,
        "total": response.count or 0,
        "comments": [{
            "comment_id": c["comment_id"],
            "article_id": c["article_id"],
            "article_title": titles.get(c["article_id"]),
            "created_at": c.get("created_at"),
            "recommendation_count": c.get("recommendation_count"),
            "snippet": make_snippet(c.get("body_text") or "", q),
        } for c in response.data],
    }


def from_env() -> Tuple[Callable[[], Corpus], CommentSearch]:
    """The corpus reader and comment search for this environment's Supabase, or unavailable stand-ins."""
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return (lambda: unavailable(NOT_CONFIGURED)), (lambda articles, q: comments_unavailable(NOT_CONFIGURED))
    from supabase import create_client  # imported here so the app runs without it

    client = create_client(url, key)
    return reader(client), (lambda articles, q: search_comments(client, articles, q))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: `34 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/corpus.py backend/tests/test_corpus.py
git commit -m "Search article comments by keyword

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task A4: Serve filters and search from the API

**Files:**
- Modify: `backend/app.py` (imports, `create_app`, `/results`, new `/search/comments`)
- Modify: `backend/tests/helpers.py:14-22`
- Modify: `backend/orchestrator/topic_counts.py` (drop the now-unused live reader)
- Modify: `backend/tests/test_topic_counts.py` (drop the reader's tests)
- Modify: `backend/run_dev_server.py:81-86`
- Test: `backend/tests/test_dashboard_routes.py` (new)

**Interfaces:**
- Consumes: everything `corpus` produces in Tasks A1–A3.
- Produces: `create_app(runner=None, read_corpus=None, search_comments=None)`; `helpers.build_client(registry=None, read_corpus=None, search_comments=None)`; `GET /api/v1/results?from&to&source_type&stakeholder&topic&q` and `GET /api/v1/search/comments?q&...` in the spec's JSON shapes.

- [ ] **Step 1: Write the failing route tests**

`backend/tests/test_dashboard_routes.py`:

```python
"""
/results and /search/comments: filters arrive as query params, bad ones
are refused with a reason, and a missing database degrades to a message
rather than a 500.
"""
from helpers import build_client
from orchestrator import corpus

ARTICLES = [
    {"id": 1, "title": "Teachers try AI tutors", "source": "Example News", "url": "https://example.com/1",
     "published_date": "2026-09-01T10:00:00+00:00", "clean_content": "Teachers say tutors help.",
     "source_type": "news_outlet", "stakeholder": "educators", "stable_topic_id": "T001", "topic": "Adoption"},
    {"id": 2, "title": "Students and cheating", "source": "A Blog", "url": "https://example.com/2",
     "published_date": "2026-08-01T10:00:00+00:00", "clean_content": "Cheating with chatbots rises.",
     "source_type": "blog", "stakeholder": "students", "stable_topic_id": "T004", "topic": "Integrity"},
]


def available():
    return {"available": True, "reason": None, "articles": ARTICLES}


class RecordingSearch:
    """Stands in for corpus.search_comments; remembers what it was asked."""

    def __init__(self, error=None):
        self.calls, self.error = [], error

    def __call__(self, articles, q):
        self.calls.append(([a["id"] for a in articles], q))
        if self.error:
            raise self.error
        return {"available": True, "reason": None, "total": 1,
                "comments": [{"comment_id": "c1", "article_id": articles[0]["id"], "snippet": q}]}


def test_results_without_filters_lists_the_whole_corpus():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results").get_json()
    assert (body["articles"]["total"], body["articles"]["corpus"]) == (2, 2)
    assert [a["id"] for a in body["articles"]["items"]] == [1, 2]
    assert body["sentiment_distribution"] == {"positive": 0.55, "neutral": 0.23, "negative": 0.22}
    assert body["filter_options"]["stakeholders"] == ["educators", "students"]


def test_results_applies_the_filters_to_articles_and_topics():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    body = client.get("/api/v1/results?stakeholder=students&q=cheating").get_json()
    assert [a["id"] for a in body["articles"]["items"]] == [2]
    assert body["articles"]["items"][0]["snippet"] == "Cheating with chatbots rises."
    assert body["top_topics"]["items"] == [{"label": "Integrity", "count": 1}]
    assert "clean_content" not in body["articles"]["items"][0]


def test_results_refuses_a_bad_date():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    response = client.get("/api/v1/results?from=yesterday")
    assert response.status_code == 400
    assert "'from' must be a date" in response.get_json()["error"]


def test_results_without_a_database_still_loads_and_says_why():
    client, _ = build_client(read_corpus=lambda: corpus.unavailable("Database down."),
                             search_comments=RecordingSearch())
    response = client.get("/api/v1/results")
    assert response.status_code == 200
    body = response.get_json()
    assert body["articles"]["available"] is False
    assert body["articles"]["reason"] == "Database down."
    assert body["top_topics"]["available"] is False


def test_comment_search_needs_a_query():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch())
    response = client.get("/api/v1/search/comments?stakeholder=students")
    assert response.status_code == 400
    assert response.get_json()["error"] == "'q' is required."


def test_comment_search_is_scoped_by_the_other_filters_but_not_by_q():
    search = RecordingSearch()
    client, _ = build_client(read_corpus=available, search_comments=search)
    # Article 1 never says "cheating", but its comments may.
    body = client.get("/api/v1/search/comments?q=cheating&stakeholder=educators").get_json()
    assert search.calls == [([1], "cheating")]
    assert body["total"] == 1


def test_a_failed_comment_search_is_reported_not_raised():
    client, _ = build_client(read_corpus=available, search_comments=RecordingSearch(error=ConnectionError("down")))
    response = client.get("/api/v1/search/comments?q=cheating")
    assert response.status_code == 200
    assert response.get_json() == {"available": False, "total": 0, "comments": [],
                                   "reason": "Could not search comments; see the backend log."}


def test_comment_search_without_a_database_says_why():
    search = RecordingSearch()
    client, _ = build_client(read_corpus=lambda: corpus.unavailable("Database down."), search_comments=search)
    body = client.get("/api/v1/search/comments?q=cheating").get_json()
    assert (body["available"], body["reason"]) == (False, "Database down.")
    assert search.calls == []


def test_without_supabase_the_dashboard_says_it_is_not_configured(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    client, _ = build_client()
    body = client.get("/api/v1/results").get_json()
    assert body["articles"]["reason"] == corpus.NOT_CONFIGURED
    assert body["top_topics"]["reason"] == corpus.NOT_CONFIGURED
```

- [ ] **Step 2: Point the test helper at the new parameters**

In `backend/tests/helpers.py`, change the signature and the `create_app` call:

```python
def build_client(registry=None, read_corpus=None, search_comments=None):
```

```python
    app = create_app(runner=runner, read_corpus=read_corpus, search_comments=search_comments)
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `python -m pytest tests/test_dashboard_routes.py -q`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument 'read_corpus'`.

- [ ] **Step 4: Wire the corpus into `backend/app.py`**

Replace the two `/api/v1/results` lines in the module docstring's STATUS list with:

```
  * /api/v1/results — the analysable articles and their topic counts,
                      filtered per request (orchestrator/corpus.py);
                      sentiment is still a hardcoded placeholder
  * /api/v1/search/comments — keyword search over article comments
```

Change the Flask import to `from flask import Flask, jsonify, request`, and replace the `topic_counts` import with the corpus module:

```python
from orchestrator import corpus
from orchestrator.routes import create_runs_blueprint
from orchestrator.supabase_store import SupabaseRunStore
```

After `logger = logging.getLogger(__name__)` add:

```python

# Shaped like what the aggregation agent will produce, but invented: no
# stage aggregates sentiment_results into /results yet.
PLACEHOLDER_SENTIMENT = {"positive": 0.55, "neutral": 0.23, "negative": 0.22}
```

Replace the whole of `create_app` (from `def create_app(` down to `return app`) with:

```python
def create_app(runner=None, read_corpus=None, search_comments=None):
    """
    Build the Flask app. Tests pass in their own runner, corpus reader and
    comment search; normal startup builds the defaults (agents and run
    store from the environment, the corpus from Supabase when it is set).
    """
    app = Flask(__name__)
    CORS(app)  # TODO: restrict origins before this leaves localhost

    if runner is None:
        coordinator = PipelineCoordinator(build_default_registry(), build_run_store())
        runner = BackgroundRunner(coordinator)
    if read_corpus is None or search_comments is None:
        default_read, default_search = corpus.from_env()
        read_corpus = read_corpus or default_read
        search_comments = search_comments or default_search
    app.register_blueprint(create_runs_blueprint(runner))

    def filters_or_400():
        """The request's filters, or a 400 response saying what is wrong with them."""
        try:
            return corpus.parse_filters(request.args), None
        except ValueError as exc:
            return None, (jsonify({"error": str(exc)}), 400)

    @app.get("/api/v1/health")
    def health():
        """Lets the front end confirm the backend is reachable."""
        return jsonify({"status": "ok"})

    @app.get("/api/v1/results")
    def get_results():
        """
        The dashboard's data, narrowed by the filter query params: from,
        to, source_type, stakeholder, topic, q (see orchestrator/corpus.py).

        Articles and top topics are real. sentiment_distribution is still
        a placeholder until the sentiment agent is wired in.

        TODO: add auth check once Session/Auth Context (SS-5) is wired in
        """
        filters, error = filters_or_400()
        if error:
            return error
        return jsonify({
            "sentiment_distribution": PLACEHOLDER_SENTIMENT,
            **corpus.results_payload(read_corpus(), filters),
        })

    @app.get("/api/v1/search/comments")
    def get_comment_search():
        """
        Comments containing `q` on the articles the other filters allow.

        `q` doesn't narrow the articles here: a comment can use a word its
        article never does.
        """
        filters, error = filters_or_400()
        if error:
            return error
        if not filters["q"]:
            return jsonify({"error": "'q' is required."}), 400
        current = read_corpus()
        if not current["available"]:
            return jsonify(corpus.comments_unavailable(current["reason"]))
        articles = corpus.filter_articles(current["articles"], {**filters, "q": ""})
        try:
            return jsonify(search_comments(articles, filters["q"]))
        except Exception:
            logger.exception("Comment search failed")
            return jsonify(corpus.comments_unavailable("Could not search comments; see the backend log."))

    return app
```

- [ ] **Step 5: Run the route tests to see them pass**

Run: `python -m pytest tests/test_dashboard_routes.py -q`
Expected: `9 passed`.

- [ ] **Step 6: Remove the live topic reader nothing calls any more**

In `backend/orchestrator/topic_counts.py`, replace the first paragraph of the docstring (lines 2–7) with:

```
The dashboard's top_topics facet: articles per topic, in the shape the
aggregation plan (docs/superpowers/plans/2026-09-29-aggregation-agent.md)
will snapshot. Until that agent exists, orchestrator/corpus.py counts
the filtered articles with top_topics() on each request.
```

replace the imports and logger (lines 15–19) with:

```python
from typing import Any, Dict, Iterable
```

and delete `read_topic_rows`, `reader` and `reader_from_env` (everything from `def read_topic_rows(` to the end of the file). Keep `Facet`, `unavailable` and `top_topics`.

In `backend/tests/test_topic_counts.py`, replace the docstring and imports (lines 1–10) with:

```python
"""
The dashboard's topic counts.

What can go wrong here is quiet: unassigned articles counted as a topic,
or no topics drawn as an empty chart.
"""
from orchestrator.topic_counts import top_topics
```

and delete the `FakeClient` class and these four tests, which covered the removed reader (their replacements are in `test_corpus.py` and `test_dashboard_routes.py`): `test_reads_every_page_even_when_the_server_caps_pages`, `test_a_failed_read_is_reported_instead_of_breaking_the_endpoint`, `test_results_serves_the_counts`, `test_results_says_why_topics_are_missing_without_supabase`.

- [ ] **Step 7: Give the dev server the no-database corpus**

In `backend/run_dev_server.py`, replace:

```python
    from app import create_app
    from orchestrator.topic_counts import unavailable

    app = create_app(
        runner=BackgroundRunner(coordinator),
        read_topics=lambda: unavailable("The dev server doesn't read the database, so there are no topic counts."),
    )
```

with:

```python
    from app import create_app
    from orchestrator import corpus

    no_data = "The dev server doesn't read the database, so there are no articles. Use python app.py for real data."
    app = create_app(
        runner=BackgroundRunner(coordinator),
        read_corpus=lambda: corpus.unavailable(no_data),
        search_comments=lambda articles, q: corpus.comments_unavailable(no_data),
    )
```

- [ ] **Step 8: Run the whole suite**

Run: `python -m pytest -q`
Expected: `152 passed` (113 before, minus 4 removed, plus 34 + 9 new). Then `grep -rn "read_topics\|reader_from_env" backend` finds nothing.

- [ ] **Step 9: Check the endpoints against the real database (read-only)**

Start the real backend on A's port, in the background:

```bash
cd backend && python -c "from app import app; app.run(port=5001)"
```

Then:

```bash
curl -s "http://localhost:5001/api/v1/results" | python -c "import sys,json; b=json.load(sys.stdin); print(b['articles']['total'], b['articles']['corpus'], b['top_topics']['counted'], b['filter_options']['stakeholders'])"
curl -s "http://localhost:5001/api/v1/results?stakeholder=educators&q=cheating" | python -c "import sys,json; b=json.load(sys.stdin); print(b['articles']['total'], b['top_topics']['items'][:2])"
curl -s "http://localhost:5001/api/v1/search/comments?q=cheating" | python -c "import sys,json; b=json.load(sys.stdin); print(b['total'], len(b['comments']))"
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5001/api/v1/results?from=2026-10-02&to=2026-10-01"
```

Expected (2026-10-08 data; counts may have grown): `328 328 135 [...7 stakeholders...]`; about `24` articles with topic items; about `82 50`; `400`. Leave the backend running for Task A6.

- [ ] **Step 10: Commit**

```bash
git add backend
git commit -m "Serve filtered articles and comment search from the API

/results now reads the analysable corpus and takes from, to,
source_type, stakeholder, topic and q. The live topic_results reader
it replaces is removed.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task A5: Hold the filters in the view state

**Files:**
- Modify: `frontend/src/api/apiClient.js` (`getResults`, new `searchComments`)
- Modify: `frontend/src/state/ViewStateContext.jsx`

**Interfaces:**
- Consumes: the endpoints from Task A4.
- Produces (from `useViewState()`): `filters` (`{from, to, source_type, stakeholder, topic, q}`, strings, `""` when unset), `setFilters(patch)`, `clearFilters()`, `results` (now carrying `articles` as an object and `filter_options`), `loading`, `error`, `commentResults` (`null` or the `/search/comments` body), `commentsLoading`, `commentsError`. Also exports `EMPTY_FILTERS`.

- [ ] **Step 1: Send the filters as query params**

In `frontend/src/api/apiClient.js`, replace the STATUS bullet about `getResults()` (lines 9–12) with:

```
 *   - getResults(filters) and searchComments(filters) are real: the
 *     backend filters the analysable articles per request. Sentiment in
 *     /results is still a hardcoded placeholder.
```

and replace `getResults` (lines 66–69) with:

```js
/** Non-empty filter values as a query string; "" when none are set. */
function toQuery(filters = {}) {
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** Dashboard results for these filters (from, to, source_type, stakeholder, topic, q). */
export async function getResults(filters) {
  return request(`/results${toQuery(filters)}`);
}

/** Comments mentioning filters.q, on the articles the other filters allow. */
export async function searchComments(filters) {
  return request(`/search/comments${toQuery(filters)}`);
}
```

- [ ] **Step 2: Add filter state to the provider**

In `frontend/src/state/ViewStateContext.jsx`:

Replace the STATUS block in the header comment (lines 7–12) with:

```
 * STATUS:
 *   - filters: held here; results and comment search reload whenever
 *     they change. /results serves real articles and topic counts;
 *     its sentiment is still a placeholder.
 *   - run status + the run-status poller: real, reading pipeline_runs.
```

Change the API import (line 22) to:

```js
import { getResults, getRun, getRuns, searchComments, startRun } from "../api/apiClient";
```

Before `export function isFinished`, add:

```js
export const EMPTY_FILTERS = { from: "", to: "", source_type: "", stakeholder: "", topic: "", q: "" };
```

(a) Directly after `const [error, setError] = useState(null);` insert:

```js

  // --- filters and comment search ---------------------------------------
  const [filters, setFilterState] = useState(EMPTY_FILTERS);
  const [commentResults, setCommentResults] = useState(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentsError, setCommentsError] = useState(null);

  // Each request takes a ticket; a response whose ticket is no longer the
  // latest is dropped. Typing a year into a date input fires several
  // changes, and a slow early response must not overwrite a later one.
  const resultsTicket = useRef(0);
  const commentsTicket = useRef(0);
```

(b) Leave the run-state block (`const [runs, setRuns]` … `const watchedRunId = useRef(null);`) as it is. Replace the three things after it — the `// TODO: accept filters once FilterPanel is built` comment, the old `loadResults` `useCallback`, and Task 0's mount effect — with:

```js
  const loadResults = useCallback(async (activeFilters = EMPTY_FILTERS) => {
    const ticket = ++resultsTicket.current;
    setLoading(true);
    setError(null);
    try {
      const data = await getResults(activeFilters);
      if (ticket === resultsTicket.current) setResults(data);
    } catch (err) {
      // Keep the last good results on screen; the error says why they didn't change.
      if (ticket === resultsTicket.current) setError(err.message);
    } finally {
      if (ticket === resultsTicket.current) setLoading(false);
    }
  }, []);

  const loadComments = useCallback(async (activeFilters) => {
    const ticket = ++commentsTicket.current;
    setCommentsError(null);
    if (!activeFilters.q) {
      setCommentResults(null);
      setCommentsLoading(false);
      return;
    }
    setCommentsLoading(true);
    try {
      const data = await searchComments(activeFilters);
      if (ticket === commentsTicket.current) setCommentResults(data);
    } catch (err) {
      if (ticket === commentsTicket.current) setCommentsError(err.message);
    } finally {
      if (ticket === commentsTicket.current) setCommentsLoading(false);
    }
  }, []);

  // Results and comments follow the filters, including the first load.
  useEffect(() => {
    loadResults(filters);
    loadComments(filters);
  }, [filters, loadResults, loadComments]);

  /** Merge a change into the filters, e.g. setFilters({ stakeholder: "educators" }). */
  const setFilters = useCallback((patch) => setFilterState((current) => ({ ...current, ...patch })), []);
  const clearFilters = useCallback(() => setFilterState(EMPTY_FILTERS), []);
```

Delete the old `// TODO: activeFilters state + setFilters()` line near the end, and add the new values to `value`:

```js
  const value = {
    results,
    loading,
    error,
    loadResults,
    filters,
    setFilters,
    clearFilters,
    commentResults,
    commentsLoading,
    commentsError,
    runs,
    activeRunId,
    selectedRun,
    runsError,
    starting,
    loadRuns,
    selectRun,
    triggerRun,
  };
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/apiClient.js frontend/src/state/ViewStateContext.jsx
git commit -m "Hold dashboard filters in the view state and reload on change

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task A6: Filter panel, article table and comment results

**Files:**
- Create: `frontend/src/components/text.jsx`
- Modify (replace the Task 0 stubs): `frontend/src/components/FilterPanel.jsx`, `frontend/src/components/ArticleTable.jsx`, `frontend/src/components/CommentResults.jsx`

**Interfaces:**
- Consumes: the `useViewState()` values from Task A5.
- Produces: the three prop-less components. `FilterPanel` and `ArticleTable` render content only (the layout gives them their card and heading); `CommentResults` renders its own `<section className="card">` with an `<h2>`, and nothing at all when there is no search. Class names used, which workstream B styles: `filter-panel`, `field`, `field-row`, `secondary` (on a button), `table-meta`, `table-scroll`, `data-table`, `snippet`, `card`, `comment-list`, `comment`, `comment-meta`, `empty-note`.

- [ ] **Step 1: Shared text helpers**

`frontend/src/components/text.jsx`:

```jsx
/**
 * Small text helpers shared by the filter panel, article table and
 * comment results.
 */

/** "trade_publication" → "Trade publication"; an em dash for nothing. */
export function humanize(code) {
  if (!code) return "—";
  const words = code.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** "2026-08-17T10:00:00+00:00" → "17 Aug 2026" in the viewer's locale; an em dash when missing. */
export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? "—"
    : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** `text` with every case-insensitive occurrence of `query` wrapped in <mark>. */
export function Highlight({ text, query }) {
  if (!text) return null;
  if (!query) return text;
  const haystack = text.toLowerCase();
  const needle = query.toLowerCase();
  const parts = [];
  let at = 0;
  for (let hit = haystack.indexOf(needle); hit !== -1; hit = haystack.indexOf(needle, at)) {
    parts.push(text.slice(at, hit), <mark key={hit}>{text.slice(hit, hit + needle.length)}</mark>);
    at = hit + needle.length;
  }
  parts.push(text.slice(at));
  return <>{parts}</>;
}
```

- [ ] **Step 2: The filter panel**

`frontend/src/components/FilterPanel.jsx`:

```jsx
/**
 * Filter panel: narrows the article table, the topic chart and the
 * comment search.
 *
 * Dropdowns and dates apply as soon as they change. The search box
 * applies on Enter (or its button), so each keystroke isn't a request.
 * The options come from the corpus (/results filter_options), not from
 * a list kept here.
 *
 * MVP (README, "MVP features — come back to these"): one value per
 * filter, and the filters are not kept in the URL.
 */
import { useEffect, useState } from "react";
import { useViewState } from "../state/ViewStateContext";
import { humanize } from "./text";

export default function FilterPanel() {
  const { filters, setFilters, clearFilters, results } = useViewState();
  const options = results?.filter_options;

  // The search box edits a draft; the q filter changes only on submit.
  const [draft, setDraft] = useState(filters.q);
  useEffect(() => setDraft(filters.q), [filters.q]);

  const field = (key) => ({
    id: `filter-${key}`,
    value: filters[key],
    onChange: (event) => setFilters({ [key]: event.target.value }),
  });
  const anySet = Object.values(filters).some(Boolean);

  return (
    <form
      className="filter-panel"
      role="search"
      aria-label="Filter articles"
      onSubmit={(event) => {
        event.preventDefault();
        setFilters({ q: draft.trim() });
      }}
    >
      <h2>Filters</h2>

      <div className="field">
        <label htmlFor="filter-q">Search articles and comments</label>
        <input
          id="filter-q"
          type="search"
          placeholder="e.g. cheating"
          minLength={2}
          maxLength={100}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit">Search</button>
      </div>

      <div className="field-row">
        <div className="field">
          <label htmlFor="filter-from">From</label>
          <input
            type="date"
            min={options?.date_min || undefined}
            max={filters.to || options?.date_max || undefined}
            {...field("from")}
          />
        </div>
        <div className="field">
          <label htmlFor="filter-to">To</label>
          <input
            type="date"
            min={filters.from || options?.date_min || undefined}
            max={options?.date_max || undefined}
            {...field("to")}
          />
        </div>
      </div>

      <Choice
        label="Source type"
        field={field("source_type")}
        choices={(options?.source_types ?? []).map((value) => ({ value, label: humanize(value) }))}
      />
      <Choice
        label="Stakeholder"
        field={field("stakeholder")}
        choices={(options?.stakeholders ?? []).map((value) => ({ value, label: humanize(value) }))}
      />
      <Choice
        label="Topic"
        field={field("topic")}
        choices={(options?.topics ?? []).map((t) => ({ value: t.id, label: t.label }))}
      />

      <button
        type="button"
        className="secondary"
        disabled={!anySet && !draft}
        onClick={() => {
          setDraft("");
          clearFilters();
        }}
      >
        Clear filters
      </button>
    </form>
  );
}

function Choice({ label, field, choices }) {
  return (
    <div className="field">
      <label htmlFor={field.id}>{label}</label>
      <select {...field}>
        <option value="">All</option>
        {choices.map(({ value, label: text }) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </div>
  );
}
```

- [ ] **Step 3: The article table**

`frontend/src/components/ArticleTable.jsx`:

```jsx
/**
 * The analysable articles that match the filters, newest first.
 *
 * No sentiment column: there is no real per-article sentiment in
 * /results yet, and a made-up value per row would read as data.
 *
 * MVP (README, "MVP features — come back to these"): every match is
 * rendered, with no paging. Fine at a few hundred rows.
 */
import { useViewState } from "../state/ViewStateContext";
import { Highlight, formatDate, humanize } from "./text";

export default function ArticleTable() {
  const { results, filters } = useViewState();
  const articles = results?.articles;
  if (!articles) return null;
  if (!articles.available) return <p className="empty-note">{articles.reason}</p>;

  return (
    <>
      <p className="table-meta">
        Showing {articles.total} of {articles.corpus} articles
      </p>
      {articles.items.length === 0 ? (
        <p className="empty-note">No articles match these filters.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Date</th>
                <th scope="col">Source</th>
                <th scope="col">Source type</th>
                <th scope="col">Stakeholder</th>
                <th scope="col">Topic</th>
              </tr>
            </thead>
            <tbody>
              {articles.items.map((a) => {
                const title = <Highlight text={a.title || "Untitled"} query={filters.q} />;
                return (
                  <tr key={a.id}>
                    <td>
                      {a.url ? (
                        <a href={a.url} target="_blank" rel="noreferrer">
                          {title}
                        </a>
                      ) : (
                        title
                      )}
                      {a.snippet && (
                        <p className="snippet">
                          <Highlight text={a.snippet} query={filters.q} />
                        </p>
                      )}
                    </td>
                    <td>{formatDate(a.published_date)}</td>
                    <td>{a.source || "—"}</td>
                    <td>{humanize(a.source_type)}</td>
                    <td>{humanize(a.stakeholder)}</td>
                    <td>{a.topic || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 4: The comment results**

`frontend/src/components/CommentResults.jsx`:

```jsx
/**
 * Comments that mention the search term, on the articles the other
 * filters allow. Renders nothing until there is a search.
 *
 * MVP (README, "MVP features — come back to these"): the newest 50
 * matches only, no paging, and plain substring matching.
 */
import { useViewState } from "../state/ViewStateContext";
import { Highlight, formatDate } from "./text";

export default function CommentResults() {
  const { filters, commentResults, commentsLoading, commentsError } = useViewState();
  if (!filters.q) return null;

  return (
    <section className="card" aria-labelledby="comments-heading" aria-busy={commentsLoading}>
      <h2 id="comments-heading">Comments</h2>
      {commentsLoading && <p className="table-meta">Searching comments…</p>}
      {commentsError && <p className="empty-note">{commentsError}</p>}
      {!commentsLoading && commentResults && !commentResults.available && (
        <p className="empty-note">{commentResults.reason}</p>
      )}
      {!commentsLoading && commentResults?.available && (
        <CommentList results={commentResults} query={filters.q} />
      )}
    </section>
  );
}

function CommentList({ results, query }) {
  const { total, comments } = results;
  if (total === 0) return <p className="empty-note">No comments mention “{query}”.</p>;
  return (
    <>
      <p className="table-meta">
        {total} comment{total === 1 ? "" : "s"} mention “{query}”
        {total > comments.length && ` (showing the newest ${comments.length})`}
      </p>
      <ul className="comment-list">
        {comments.map((c) => (
          <li key={c.comment_id} className="comment">
            <p className="snippet">
              <Highlight text={c.snippet} query={query} />
            </p>
            <p className="comment-meta">
              On <em>{c.article_title || `article ${c.article_id}`}</em> · {formatDate(c.created_at)} ·{" "}
              {c.recommendation_count ?? 0} recommend{c.recommendation_count === 1 ? "" : "s"}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
```

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 6: Check it in a browser against real data (read-only)**

With A's backend from Task A4 step 9 still on port 5001, start Vite in the background:

```bash
cd frontend && VITE_API_URL=http://localhost:5001/api/v1 npx vite --port 5174 --strictPort
```

Render the page headlessly (don't touch the Pipeline runs controls):

```bash
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
OUT="$(cygpath -w "$TEMP")"
"$EDGE" --headless=new --disable-gpu --force-prefers-reduced-motion --hide-scrollbars \
  --user-data-dir="$OUT\\edge-mvp-a" --window-size=1280,2400 --virtual-time-budget=15000 \
  --dump-dom http://localhost:5174/ > "$TEMP/mvp-a.html"
grep -o "Showing [0-9]* of [0-9]* articles" "$TEMP/mvp-a.html"
"$EDGE" --headless=new --disable-gpu --force-prefers-reduced-motion --hide-scrollbars \
  --user-data-dir="$OUT\\edge-mvp-a" --window-size=1280,2400 --virtual-time-budget=15000 \
  --screenshot="$OUT\\mvp-a.png" http://localhost:5174/
```

Expected: `Showing 328 of 328 articles`; open `$TEMP/mvp-a.png` with the Read tool and check the table lists real titles and the topic chart has bars. Layout is still unstyled on this branch; that is workstream B's.

Then check the interactions the headless render can't, by driving them through the API the components call (the same requests `setFilters` triggers):

```bash
curl -s "http://localhost:5001/api/v1/results?stakeholder=educators" | python -c "import sys,json; b=json.load(sys.stdin); print(b['articles']['total'], b['top_topics']['counted'])"
curl -s -G "http://localhost:5001/api/v1/search/comments" --data-urlencode 'q=(yes, really)' | python -c "import sys,json; print(json.load(sys.stdin)['available'])"
curl -s -G "http://localhost:5001/api/v1/search/comments" --data-urlencode 'q="AI"' | python -c "import sys,json; print(json.load(sys.stdin)['available'])"
curl -s "http://localhost:5001/api/v1/results?from=2026-10-02&to=2026-10-01"
```

Expected: a smaller total for educators, with a different topic count; `True` twice (no 500 on commas, parentheses or quotes); a 400 body `{"error": "'from' must not be after 'to'."}`, which `loadResults` surfaces through `error` while keeping the last results.

Stop both background servers when done.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components
git commit -m "Add the filter panel, article table and comment search results

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 8: Report the shortcuts**

In the final report, list any shortcut taken beyond the spec's "MVP shortcuts" table, with its ceiling and the better version, so the coordinator can add it to the README.

---

# Workstream B: visual redesign

Worktree: `C:/Users/ravid/Projects/ClassroomScope-mvp-redesign`, branch `dashboard-mvp-redesign`. B never edits `FilterPanel.jsx`, `ArticleTable.jsx`, `CommentResults.jsx`, `text.jsx`, `ViewStateContext.jsx`, `apiClient.js` or anything in `backend/`. On this branch those three components are still Task 0's stubs and `/results` still has the old shape (`articles` is a two-row list, which nothing on the page reads any more); workstream A's work arrives at the merge.

## Task B1: Design tokens and base styles

**Files:**
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/main.jsx`, `frontend/index.html`

**Interfaces:**
- Produces: CSS custom properties on `:root` and every class the spec and Tasks A6/B2/B3 use: layout (`topbar`, `brand`, `brand-name`, `brand-tagline`, `tabs`, `tab`, `layout`, `sidebar`, `main`, `is-loading`, `chart-row`, `page`, `page-header`, `page-subtitle`), surfaces (`card`, `card-subtitle`, `muted`, `placeholder-note`, `notice`, `empty-note`, `chart`, `chart-donut`), workstream A's (`filter-panel`, `field`, `field-row`, `secondary`, `table-meta`, `table-scroll`, `data-table`, `snippet`, `comment-list`, `comment`, `comment-meta`), and the console's (`badge`, `console-actions`, `console-grid`, `run-detail`, `run-list`, `run-summary`, `run-title`, `run-notes`, `stub-tag`, `warn`, `stub-note`, `detail-block`, `detail-title`, `error`, `recovered`, `run-list-title`, `run-items`, `run-item`, `live-tag`, `run-time`).

- [ ] **Step 1: Write the stylesheet**

`frontend/src/styles.css`:

```css
/*
 * ClassroomScope styles: tokens on :root, base element styles, then
 * layout and components, in one file.
 *
 * The status colours mirror components/statusStyles.js, which the
 * charts and badges read from JS. Change both together.
 *
 * Base element styles sit inside :where(), which carries no specificity,
 * so any class overrides them without !important.
 */

:root {
  /* Status palette (statusStyles.js) */
  --blue: #1f4e79;
  --blue-bg: #e1edf8;
  --blue-border: #b9d4ec;
  --blue-hover: #173d60;
  --green: #1e6b3a;
  --green-bg: #e4f3e9;
  --green-border: #bfe0cb;
  --amber: #8a5a00;
  --amber-bg: #fdf1dc;
  --amber-border: #f0d9a8;
  --red: #a33a34;
  --red-bg: #fbe7e6;
  --red-border: #f0c4c1;
  --grey: #4a4a4a;
  --grey-bg: #ececec;
  --grey-border: #d4d4d4;

  /* Surfaces and text */
  --page: #f3f5f8;
  --surface: #ffffff;
  --subtle: #f8fafc;
  --line: #dde3ea;
  --line-soft: #edf0f4;
  --control-border: #8794a1; /* 3:1 against white, the minimum for a control's edge */
  --text: #1c2430;
  --muted: #566170; /* 6:1 on --page */
  --on-blue-muted: #d6e4f2;
  --highlight: #ffe58f;

  /* Shape and space */
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 2px rgb(16 24 40 / 6%), 0 1px 3px rgb(16 24 40 / 8%);
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;

  /* Type */
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
  --text-xs: 12px;
  --text-sm: 13px;
  --text-md: 14px;
  --text-lg: 17px;
  --text-xl: 22px;
}

/* --- base ---------------------------------------------------------------- */

*,
*::before,
*::after {
  box-sizing: border-box;
}

:where(body) {
  margin: 0;
  font: var(--text-md) / 1.5 var(--font);
  color: var(--text);
  background: var(--page);
  -webkit-font-smoothing: antialiased;
}

:where(h1, h2, h3) {
  margin: 0;
  font-weight: 650;
  line-height: 1.25;
}
:where(h1) {
  font-size: var(--text-xl);
}
:where(h2) {
  font-size: var(--text-lg);
}
:where(p) {
  margin: 0;
}
:where(a) {
  color: var(--blue);
}
:where(code) {
  font-family: var(--mono);
  font-size: 0.92em;
}
:where(mark) {
  padding: 0 1px;
  color: inherit;
  background: var(--highlight);
  border-radius: 2px;
}

:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}

:where(input, select) {
  width: 100%;
  min-width: 0;
  padding: 7px 10px;
  font: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--control-border);
  border-radius: var(--radius-sm);
}
:where(input:hover, select:hover) {
  border-color: var(--muted);
}

:where(button) {
  padding: 8px 14px;
  font: inherit;
  font-weight: 600;
  color: #fff;
  background: var(--blue);
  border: 1px solid var(--blue);
  border-radius: var(--radius-sm);
  cursor: pointer;
}
:where(button:hover:not(:disabled)) {
  background: var(--blue-hover);
}
:where(button:disabled) {
  background: #9bb4c9;
  border-color: #9bb4c9;
  cursor: not-allowed;
}
:where(button.secondary) {
  color: var(--blue);
  background: var(--surface);
  border-color: var(--blue-border);
}
:where(button.secondary:hover:not(:disabled)) {
  background: var(--blue-bg);
}
:where(button.secondary:disabled) {
  color: var(--muted);
  background: var(--surface);
  border-color: var(--line);
}

/* --- layout -------------------------------------------------------------- */

.topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3) var(--space-5);
  padding: var(--space-3) var(--space-5);
  color: #fff;
  background: var(--blue);
}
.brand {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-1) var(--space-3);
  margin-right: auto;
}
.brand-name {
  font-size: var(--text-lg);
  font-weight: 700;
  letter-spacing: 0.01em;
}
.brand-tagline {
  font-size: var(--text-sm);
  color: var(--on-blue-muted);
}
.tabs {
  display: flex;
  gap: var(--space-1);
}
.tab {
  padding: 6px 14px;
  font: inherit;
  font-weight: 600;
  color: #fff;
  background: transparent;
  border: 1px solid rgb(255 255 255 / 35%);
  border-radius: 999px;
  cursor: pointer;
}
.tab:hover {
  background: rgb(255 255 255 / 12%);
}
.tab[aria-pressed="true"] {
  color: var(--blue);
  background: #fff;
  border-color: #fff;
}
.tab:focus-visible {
  outline-color: #fff;
}

.layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: start;
  gap: var(--space-5);
  max-width: 1440px;
  margin: 0 auto;
  padding: var(--space-5);
}
.sidebar {
  position: sticky;
  top: var(--space-5);
  max-height: calc(100vh - 2 * var(--space-5));
  overflow: auto;
}
.main {
  display: grid;
  gap: var(--space-5);
  min-width: 0;
  transition: opacity 0.15s;
}
.main.is-loading {
  opacity: 0.6;
}
.chart-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(340px, 100%), 1fr));
  gap: var(--space-5);
}
.page {
  max-width: 1440px;
  margin: 0 auto;
  padding: var(--space-5);
}
.page-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-4);
}
.page-subtitle {
  font-size: var(--text-sm);
  color: var(--muted);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-4);
    padding: var(--space-4);
  }
  .sidebar {
    position: static;
    max-height: none;
  }
  .page {
    padding: var(--space-4);
  }
}

@media (prefers-reduced-motion: reduce) {
  .main {
    transition: none;
  }
}

/* --- surfaces ------------------------------------------------------------ */

.card {
  min-width: 0;
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.card > h2 {
  margin-bottom: var(--space-3);
}
.card-subtitle,
.table-meta {
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--muted);
}
.muted {
  font-size: var(--text-sm);
  color: var(--muted);
}
.placeholder-note,
.notice {
  max-width: 70ch;
  margin-bottom: var(--space-3);
  padding: 6px 10px;
  font-size: var(--text-xs);
  color: var(--amber);
  background: var(--amber-bg);
  border: 1px solid var(--amber-border);
  border-radius: var(--radius-sm);
}
.notice {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-md);
}
.notice.error {
  color: var(--red);
  background: var(--red-bg);
  border-color: var(--red-border);
}
.empty-note {
  padding: var(--space-5) var(--space-4);
  font-size: var(--text-sm);
  color: var(--muted);
  text-align: center;
  background: var(--subtle);
  border: 1px dashed var(--line);
  border-radius: var(--radius-sm);
}
.chart {
  max-width: 760px;
}
.chart-donut {
  max-width: 480px;
  margin: 0 auto;
}
.recharts-text {
  font-family: var(--font);
  font-size: var(--text-sm);
}

/* --- filter panel -------------------------------------------------------- */

.filter-panel {
  display: grid;
  gap: var(--space-4);
}
.field {
  display: grid;
  gap: var(--space-1);
  min-width: 0;
}
.field > label {
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}
.field-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}

/* --- tables -------------------------------------------------------------- */

.table-scroll {
  max-height: 640px;
  overflow: auto;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-sm);
}
.data-table {
  width: 100%;
  font-size: var(--text-md);
  border-collapse: collapse;
}
.data-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 9px 12px;
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: left;
  text-transform: uppercase;
  white-space: nowrap;
  color: var(--muted);
  background: var(--subtle);
  border-bottom: 1px solid var(--line);
}
.data-table td {
  padding: 10px 12px;
  vertical-align: top;
  border-bottom: 1px solid var(--line-soft);
}
.data-table tbody tr:last-child td {
  border-bottom: 0;
}
.data-table tbody tr:hover {
  background: var(--subtle);
}
.data-table td:first-child {
  min-width: 260px;
}
.data-table a {
  font-weight: 600;
  text-decoration: none;
}
.data-table a:hover {
  text-decoration: underline;
}
.snippet {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
  color: var(--muted);
}

/* --- comments ------------------------------------------------------------ */

.comment-list {
  display: grid;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}
.comment {
  padding: var(--space-1) 0 var(--space-1) var(--space-3);
  border-left: 3px solid var(--blue-border);
}
.comment .snippet {
  margin: 0;
  font-size: var(--text-md);
  color: var(--text);
}
.comment-meta {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  color: var(--muted);
}

/* --- status badge -------------------------------------------------------- */

.badge {
  display: inline-block;
  padding: 2px 8px;
  font-size: var(--text-xs);
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
  border: 1px solid;
  border-radius: 999px;
}

/* --- pipeline runs console ----------------------------------------------- */

.console-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.console-grid {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-4);
}
.run-detail {
  flex: 2 1 460px;
}
.run-list {
  flex: 1 1 260px;
  padding: var(--space-4);
}
.run-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
}
.run-title {
  font-size: var(--text-lg);
}
.run-notes {
  margin-bottom: var(--space-3);
  font-size: var(--text-sm);
  color: var(--muted);
}
.stub-tag {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--amber);
}
.warn {
  color: var(--amber);
}
.stub-note {
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--amber);
}
.detail-block {
  margin-top: var(--space-3);
}
.detail-title {
  font-size: var(--text-sm);
}
.detail-block.error .detail-title {
  color: var(--red);
}
.detail-block.recovered .detail-title {
  color: var(--amber);
}
.detail-block p {
  margin-top: 6px;
  padding: 6px 8px;
  font: var(--text-xs) / 1.45 var(--mono);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--subtle);
  border: 1px solid var(--line-soft);
  border-left: 3px solid var(--grey-border);
  border-radius: 4px;
}
.detail-block.error p {
  border-left-color: var(--red);
}
.detail-block.recovered p {
  border-left-color: var(--amber);
}
.run-list-title {
  margin-bottom: var(--space-2);
  font-size: var(--text-md);
}
.run-items {
  margin: 0;
  padding: 0;
  list-style: none;
}
.run-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  margin-bottom: 2px;
  padding: 7px 8px;
  font: inherit;
  font-size: var(--text-sm);
  font-weight: 400;
  text-align: left;
  color: var(--text);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
.run-item:hover {
  background: var(--subtle);
}
.run-item[aria-pressed="true"] {
  background: var(--blue-bg);
  border-color: var(--blue-border);
}
.live-tag {
  font-weight: 600;
  color: var(--blue);
}
.run-time {
  display: block;
  font-size: 11px;
  color: var(--muted);
}
```

- [ ] **Step 2: Load it, and make the page scale on phones**

`frontend/src/main.jsx` — add the import after the `App` import:

```jsx
import App from "./App.jsx";
import "./styles.css";
```

`frontend/index.html` — replace the `<head>` contents:

```html
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ClassroomScope</title>
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds; `dist/assets/` contains a `.css` file.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles.css frontend/src/main.jsx frontend/index.html
git commit -m "Add the dashboard's design tokens and base styles

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task B2: Dashboard layout, tabs and charts

**Files:**
- Modify (rewrite): `frontend/src/components/DashboardShell.jsx`
- Modify: `frontend/src/components/VisualizationViews.jsx:35,59`
- Modify: `frontend/src/components/StatusBadge.jsx`

**Interfaces:**
- Consumes: classes from Task B1; `FilterPanel`, `ArticleTable`, `CommentResults` (Task 0 stubs here, Task A6 after the merge); `useViewState()` → `results`, `loading`, `error`.
- Produces: the two-tab page. `ArticleTable` sits inside an Articles card that B provides; `CommentResults` is placed bare (it renders its own card).

- [ ] **Step 1: Rewrite `frontend/src/components/DashboardShell.jsx`**

```jsx
/**
 * Dashboard Shell — page layout (Section 3 of design doc).
 *
 * Two views behind a pair of tabs: the dashboard (filters, charts,
 * articles, comment search) and the pipeline runs console. Everything
 * reads from ViewStateContext, which reloads whenever the filters
 * change; nothing here fetches.
 *
 * STATUS:
 *   - Top topics, the article table and comment search are real,
 *     filtered by the backend (orchestrator/corpus.py).
 *   - Sentiment is still a hardcoded placeholder in /results, labelled
 *     as such rather than left to look real.
 *
 * NOT built yet: ExportControls, login. See design doc Section 2.
 */
import { useState } from "react";
import { useViewState } from "../state/ViewStateContext";
import AdminConsole from "./AdminConsole";
import ArticleTable from "./ArticleTable";
import CommentResults from "./CommentResults";
import FilterPanel from "./FilterPanel";
import { SentimentDonut, TopTopicsBar } from "./VisualizationViews";

const VIEWS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "runs", label: "Pipeline runs" },
];

export default function DashboardShell() {
  const [view, setView] = useState("dashboard");

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="brand-name">ClassroomScope</span>
          <span className="brand-tagline">Generative AI in education, as the news and its readers see it</span>
        </div>
        <nav className="tabs" aria-label="Views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              className="tab"
              aria-pressed={view === v.id}
              onClick={() => setView(v.id)}
            >
              {v.label}
            </button>
          ))}
        </nav>
      </header>

      {view === "dashboard" ? (
        <Dashboard />
      ) : (
        <div className="page">
          <AdminConsole />
        </div>
      )}
    </>
  );
}

function Dashboard() {
  const { results, loading, error } = useViewState();

  return (
    <div className="layout">
      <aside className="sidebar card">
        <FilterPanel />
      </aside>

      <main className={`main${loading && results ? " is-loading" : ""}`} aria-busy={loading}>
        {error && (
          <p className="notice error" role="alert">
            {error}
          </p>
        )}
        {!results && loading && <p className="empty-note">Loading results…</p>}

        {results && (
          <>
            <div className="chart-row">
              <section className="card">
                <h2>Sentiment toward GAI in education</h2>
                <PlaceholderNote>
                  Placeholder figures, hardcoded in <code>/results</code> — not computed from the
                  corpus, and the filters don't change them. Nothing aggregates{" "}
                  <code>sentiment_results</code> into this endpoint yet.
                </PlaceholderNote>
                <SentimentDonut distribution={results.sentiment_distribution} />
              </section>

              <section className="card">
                <h2>Top topics</h2>
                <TopTopics facet={results.top_topics} />
              </section>
            </div>

            <section className="card">
              <h2>Articles</h2>
              <ArticleTable />
            </section>

            <CommentResults />
          </>
        )}
      </main>
    </div>
  );
}

/**
 * Topic counts for the filtered articles, or the reason there are none.
 * Says how many fit no topic: over half do, and a chart of only the
 * assigned ones would hide that.
 */
function TopTopics({ facet }) {
  if (!facet.available) return <p className="empty-note">{facet.reason}</p>;
  const total = facet.counted + facet.unassigned;
  return (
    <>
      <p className="card-subtitle">
        {facet.counted} of {total} matching article(s) have a topic; {facet.unassigned} don't fit any
        topic yet.
      </p>
      <TopTopicsBar topics={facet.items} />
    </>
  );
}

/** Marks a section as showing data the pipeline did not produce. */
function PlaceholderNote({ children }) {
  return <p className="placeholder-note">{children}</p>;
}
```

- [ ] **Step 2: Give the charts classes instead of inline widths**

In `frontend/src/components/VisualizationViews.jsx`, change line 35:

```jsx
    <div className="chart chart-donut">
```

and line 59:

```jsx
    <div className="chart">
```

- [ ] **Step 3: Move the badge's fixed styles into the stylesheet**

`frontend/src/components/StatusBadge.jsx`, replace the component:

```jsx
export default function StatusBadge({ map, status, title }) {
  const s = statusStyle(map, status);
  // Shape lives in styles.css (.badge); only the status colours are computed here.
  return (
    <span title={title} className="badge" style={{ color: s.fg, background: s.bg, borderColor: s.border }}>
      {s.label}
    </span>
  );
}
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Look at it at desktop and phone width**

Start the backend on B's port with real data (read-only), and Vite, both in the background:

```bash
cd backend && python -c "from app import app; app.run(port=5002)"
cd frontend && VITE_API_URL=http://localhost:5002/api/v1 npx vite --port 5175 --strictPort
```

Screenshot both widths:

```bash
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
OUT="$(cygpath -w "$TEMP")"
for W in 1280 375; do
  "$EDGE" --headless=new --disable-gpu --force-prefers-reduced-motion --hide-scrollbars \
    --user-data-dir="$OUT\\edge-mvp-b" --window-size=$W,1800 --virtual-time-budget=15000 \
    --screenshot="$OUT\\mvp-b-$W.png" http://localhost:5175/
done
```

Open both PNGs with the Read tool. Expected at 1280: blue top bar with the two tabs, the filter sidebar card on the left, Sentiment and Top topics cards side by side with a labelled donut and bars, then the Articles card (still the stub note on this branch). At 375: the sidebar stacks above the cards, the charts stack, and nothing scrolls sideways. Fix anything that overflows or overlaps before committing.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/DashboardShell.jsx frontend/src/components/VisualizationViews.jsx frontend/src/components/StatusBadge.jsx
git commit -m "Lay the dashboard out as tabs, a filter sidebar and cards

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

## Task B3: Restyle the pipeline runs console

**Files:**
- Modify (rewrite): `frontend/src/components/AdminConsole.jsx`

**Interfaces:**
- Consumes: classes from Task B1; `StatusBadge` from Task B2; `useViewState()` run values (unchanged).
- Produces: the same console behaviour with class-based styling and a page heading.

- [ ] **Step 1: Rewrite `frontend/src/components/AdminConsole.jsx`**

Behaviour is unchanged; only the markup and styling move to classes.

```jsx
/**
 * Admin Console — start a pipeline run and watch it progress.
 *
 * It reads pipeline_runs and pipeline_stage_runs through the run
 * endpoints, which return genuine rows.
 *
 * Three things the backend does that this UI has to account for:
 *
 *   * POST /runs returns 202 immediately and the pipeline keeps going on
 *     a server thread. So starting a run shows it at 'running' with every
 *     stage 'pending' — that is correct, not a stall. The poller in
 *     ViewStateContext fills it in.
 *   * Only one run may be active. A second POST returns 409 with the
 *     active run's id; the store switches to that run rather than just
 *     showing an error.
 *   * Three of the seven stages are stubs (sentiment, stance,
 *     aggregation). They succeed in about a millisecond without doing
 *     anything, which looks identical to real work from here — hence the
 *     note under the stage table.
 *
 * TODO(auth): the whole panel should be admin-only once login (SS-5)
 * exists. The backend has the matching TODO on POST /runs.
 */
import { useViewState } from "../state/ViewStateContext";
import StatusBadge from "./StatusBadge";
import {
  RUN_STATUS,
  STAGE_STATUS,
  formatDuration,
  formatTime,
} from "./statusStyles";

// Stages that are stubs everywhere today: sentiment is a standalone
// script the pipeline can't call yet, and stance and aggregation have
// no implementation. Flagged so nobody reads "succeeded" as "analysed
// something". Topic is left out: it runs for real wherever its model
// was pulled with Git LFS. Where it wasn't, topic is a stub this list
// can't see; the fix is for the backend to report which agent ran.
const STUBBED_STAGES = ["sentiment", "stance", "aggregation"];

export default function AdminConsole() {
  const {
    runs,
    activeRunId,
    selectedRun,
    runsError,
    starting,
    selectRun,
    triggerRun,
  } = useViewState();

  const isActive = activeRunId !== null;

  return (
    <section aria-labelledby="console-heading">
      <div className="page-header">
        <h1 id="console-heading">Pipeline runs</h1>
        <span className="page-subtitle">
          Live data from <code>pipeline_runs</code>
        </span>
      </div>

      <div className="console-actions">
        <button type="button" onClick={() => triggerRun("manual")} disabled={starting || isActive}>
          {starting ? "Starting…" : isActive ? "Run in progress…" : "Start a run"}
        </button>
        {isActive && <span className="muted">Only one run may be active at a time.</span>}
      </div>

      {runsError && (
        <p className="notice" role="status">
          {runsError}
        </p>
      )}

      <div className="console-grid">
        <RunDetail run={selectedRun} />
        <RunList runs={runs} selectedId={selectedRun?.id} activeRunId={activeRunId} onSelect={selectRun} />
      </div>
    </section>
  );
}

function RunDetail({ run }) {
  if (!run) {
    return (
      <div className="card run-detail">
        <p className="muted">No runs yet. Start one to see it here.</p>
      </div>
    );
  }

  const stubbedThatRan = run.stages.filter(
    (s) => STUBBED_STAGES.includes(s.stage_name) && s.status === "succeeded"
  );

  return (
    <div className="card run-detail">
      <div className="run-summary">
        <strong className="run-title">Run #{run.id}</strong>
        <StatusBadge map={RUN_STATUS} status={run.status} />
        <span className="muted">
          {run.trigger_type} · started {formatTime(run.started_at)} ·{" "}
          {formatDuration(run.started_at, run.finished_at)}
          {run.articles_collected != null && ` · ${run.articles_collected} article(s)`}
        </span>
      </div>

      {run.notes && <p className="run-notes">{run.notes}</p>}

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Stage</th>
              <th scope="col">Status</th>
              <th scope="col">Attempt</th>
              <th scope="col">Duration</th>
            </tr>
          </thead>
          <tbody>
            {run.stages.map((stage) => (
              <tr key={stage.id}>
                <td>
                  {stage.stage_name}
                  {STUBBED_STAGES.includes(stage.stage_name) && (
                    <span
                      className="stub-tag"
                      title="No agent implementation yet — this stage reports success without doing work"
                    >
                      stub
                    </span>
                  )}
                </td>
                <td>
                  <StatusBadge map={STAGE_STATUS} status={stage.status} />
                </td>
                <td className={stage.attempt > 1 ? "warn" : undefined}>
                  {stage.attempt || "—"}
                  {stage.attempt > 1 && " (retried)"}
                </td>
                <td>{formatDuration(stage.started_at, stage.finished_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <StageDetails stages={run.stages} />

      {stubbedThatRan.length > 0 && (
        <p className="stub-note">
          {stubbedThatRan.length} stage(s) marked <em>stub</em> reported success without
          analysing anything — no agent is implemented for them yet.
        </p>
      )}
    </div>
  );
}

/**
 * The text the coordinator recorded against a stage.
 *
 * `error_detail` is not only set on failures. When a stage's primary
 * agent fails and its fallback succeeds, the coordinator records *why*
 * the fallback was needed — on a stage whose status is 'succeeded'.
 * Listing that under a heading called "Errors" would report a recovery
 * as a failure, so the two are separated.
 */
function StageDetails({ stages }) {
  const withDetail = stages.filter((s) => s.error_detail);
  if (withDetail.length === 0) return null;

  const failures = withDetail.filter((s) => s.status === "failed");
  const recoveries = withDetail.filter((s) => s.status !== "failed");

  return (
    <>
      {failures.length > 0 && <DetailBlock title="Errors" stages={failures} tone="error" />}
      {recoveries.length > 0 && <DetailBlock title="Recovered" stages={recoveries} tone="recovered" />}
    </>
  );
}

function DetailBlock({ title, stages, tone }) {
  return (
    <div className={`detail-block ${tone}`}>
      <strong className="detail-title">{title}</strong>
      {stages.map((s) => (
        <p key={s.id}>
          <strong>{s.stage_name}:</strong> {s.error_detail}
        </p>
      ))}
    </div>
  );
}

function RunList({ runs, selectedId, activeRunId, onSelect }) {
  return (
    <div className="card run-list">
      <h2 className="run-list-title">Recent runs</h2>
      {runs.length === 0 && <p className="muted">None yet.</p>}
      <ul className="run-items">
        {runs.map((run) => (
          <li key={run.id}>
            <button
              type="button"
              className="run-item"
              aria-pressed={run.id === selectedId}
              onClick={() => onSelect(run.id)}
            >
              <span>
                #{run.id}
                {run.id === activeRunId && <span className="live-tag"> · live</span>}
                <span className="run-time">{formatTime(run.started_at)}</span>
              </span>
              <StatusBadge map={RUN_STATUS} status={run.status} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: build succeeds. `grep -n "style={{" frontend/src/components/*.jsx` lists only `StatusBadge.jsx` (computed colours).

- [ ] **Step 3: Look at the console**

With B's servers from Task B2 still running: the console sits behind the second tab, which a headless screenshot can't click, so open it by default for one render:

1. Temporarily change `useState("dashboard")` to `useState("runs")` in `DashboardShell.jsx` (do not commit this).
2. Screenshot at 1280 and 375 as in Task B2 step 5, to `mvp-b-runs-1280.png` and `mvp-b-runs-375.png`.
3. Revert the line (`git diff` shows only the AdminConsole rewrite afterwards).

Expected: "Pipeline runs" heading, the Start a run button (do NOT click it), the run detail card with its stage table and badges, and the Recent runs list beside it at 1280 and below it at 375, with no sideways scroll.

Stop both background servers when done.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AdminConsole.jsx
git commit -m "Restyle the pipeline runs console with the shared classes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Report the shortcuts**

In the final report, list any shortcut taken beyond the spec's "MVP shortcuts" table (e.g. no dark mode, view not in the URL), with its ceiling and the better version, so the coordinator can add it to the README.

---

# Task C (coordinator): Merge, document, verify

**Files:**
- Modify: `README.md` (new "MVP features — come back to these" section; refresh "Next steps")
- Modify: `NEXT_STEPS.md:5-6` (the dashboard no longer shows only made-up numbers)

- [ ] **Step 1: Merge both workstreams into `dashboard-mvp`**

In the `dashboard-mvp` worktree:

```bash
git merge --no-ff dashboard-mvp-filters -m "Merge workstream A: filters and keyword search"
git merge --no-ff dashboard-mvp-redesign -m "Merge workstream B: visual redesign"
```

Expected: one conflict, in the branch note at the top of `README.md` (each branch rewrote it). Delete all the branch notes there, since the work they describe is done, and keep the rest of the file. Nothing else should conflict: the workstreams own disjoint files. Check line endings with `git diff --check`.

- [ ] **Step 2: Check the joined page**

Run the backend suite (`python -m pytest -q`, expect `152 passed`), `npm ci && npm run build`, then render the merged app on ports 5001/5174 as in Task A6 step 6, at 1280 and 375. Expected: `Showing 328 of 328 articles` in the styled table, and the filter sidebar populated with the 4 source types, 7 stakeholders and the topics. Then drive the page in real time over the Chrome DevTools Protocol (Node 24's global `WebSocket`, Edge started with `--remote-debugging-port`): pick a stakeholder and confirm the count and the topic chart change; type `cheating`, press Enter, and screenshot the snippets and the Comments card.

- [ ] **Step 3: Write the README's MVP section**

Add before `## Next steps (planned)` in `README.md`:

```markdown
## MVP features — come back to these

The filter panel, keyword search and visual redesign (October 2026) are
MVPs: they work end to end, but each takes shortcuts on purpose. Design:
`docs/superpowers/specs/2026-10-08-dashboard-filters-redesign-design.md`.

| Feature | Shortcut | Ceiling | Better version |
|---|---|---|---|
| Filters | Corpus read from 4 tables and filtered in Python per request, behind a 60s cache (`orchestrator/corpus.py`) | Slows as the corpus grows; up to 60s stale after a run | Aggregation snapshot or a Postgres view/RPC |
| Filters | One value per filter | Can't compare two stakeholders | Multi-select |
| Filters | Not kept in the URL | A filtered view can't be shared or bookmarked | Sync filters to the query string |
| Filters | Classification merge: any classifier beats `baseline_keyword` | Hides disagreement between classifiers | Record a chosen classifier per article in the pipeline |
| Article table | Every match rendered, no paging | Fine at hundreds, not thousands | Server-side paging |
| Search | Case-insensitive substring, first match only | No ranking, stemming or phrases | Postgres full-text search (`tsvector`) with ranking |
| Search | `*` acts as a wildcard (PostgREST has no escape for it) | `a*b` matches more than it says | Search through an RPC function |
| Search | Comment search capped at the newest 50, no paging; article IDs sent in the URL | Can't browse all matches; breaks past ~1,500 articles | Paging, and an RPC taking the filters |
| Dashboard | Sentiment donut is a hardcoded placeholder | Not real data, and filters don't move it | Aggregate `sentiment_results` once the agent is wired in |
| Frontend | No frontend tests | Regressions caught by eye | Vitest + Testing Library |
```

Append a row for each extra shortcut workstreams A and B reported.

In the same file, replace item 1 under `## Next steps (planned)` ("Build FilterPanel and wire it into ViewStateContext") with "Work through the MVP table above", and update any other line that says filters are not built.

- [ ] **Step 4: Update `NEXT_STEPS.md`**

Change "and the dashboard still shows made-up numbers" (line 5–6) to "and the dashboard's sentiment chart still shows made-up numbers".

- [ ] **Step 5: Commit**

```bash
git add README.md NEXT_STEPS.md
git commit -m "Document the dashboard MVP's shortcuts in the README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Clean up the workstream worktrees**

```bash
git worktree remove ../ClassroomScope-mvp-filters
git worktree remove ../ClassroomScope-mvp-redesign
```

(`backend/.env` and `node_modules` are untracked; use `--force` only after confirming `git -C <worktree> status` shows nothing else.)
