# Dashboard MVP: real articles, filters, keyword search, redesign

Date: 2026-10-08. Status: approved design, MVP scope.

## Goal

Make the dashboard show the real corpus and let a viewer narrow it, and
make it presentable for a demo. Three features, built as MVPs that work
end to end; the shortcuts each one takes are listed below and go into
the README so we come back to them.

1. **Filter panel.** The article table lists the 328 analysable
   articles instead of two hardcoded rows. Filters for date range,
   source type, stakeholder and topic update both the topic chart and
   the table.
2. **Keyword search.** One search box in the filter panel searches
   article titles and text and the 29,658 article comments, showing a
   snippet around each match.
3. **Visual redesign, demo-ready polish.** Dashboard layout with a
   filter sidebar, chart cards and a styled table; consistent type and
   spacing; the existing status palette kept.

Sentiment stays a placeholder (the donut keeps its "placeholder" note)
until the sentiment agent is wired into the pipeline.

## Non-goals

- No database migration, view or RPC function on the shared Supabase.
- No pagination, multi-select filters, ranked full-text search, URL
  state, export, or login.
- Reddit posts and comments (`reddit_posts`, `reddit_comments`) are not
  searched: they are not linked to articles.
- No new npm or pip dependencies.

## Data

All reads are read-only, through the Supabase client the backend
already uses (`SUPABASE_URL` / `SUPABASE_KEY`).

| What | Where |
|---|---|
| Analysable articles | `articles` where `llm_relevant = true` and `processing_status = 'success'` (328 on 2026-10-08) |
| Article fields | `id, title, source, url, published_date, clean_content` |
| Source type, stakeholder | `classification_results.source_type`, `.stakeholder_category` |
| Topic | `topic_results.stable_topic_id`, `.topic` |
| Comments | `comments(comment_id, article_id, body_text, created_at, recommendation_count)` (29,658 rows) |

Merge rules, one value per article:

- **Classification.** Most articles have two rows: `gpt-5.6-luna` and
  `baseline_keyword`. Any classifier other than `baseline_keyword` wins;
  ties go to the newest `classified_at`. No row: `source_type` and
  `stakeholder` are `null`.
- **Topic.** The newest `topic_results` row (highest `id`) for the
  article. No row, or a row with no `stable_topic_id`: unassigned.

Values seen on 2026-10-08: source types `blog, trade_publication,
news_outlet, academic`; stakeholders `students, educators,
administrators, policymakers, researchers, parents, undetermined`.
The filter options come from the data, not from these lists.

## Backend

### `backend/orchestrator/corpus.py` (new)

Modelled on `orchestrator/topic_counts.py`.

- `read_corpus(client) -> List[dict]`: the analysable articles with
  `source_type`, `stakeholder`, `stable_topic_id` and `topic` attached
  by the merge rules above. Pages every table read the way
  `read_topic_rows` does (PostgREST caps each response).
- `filter_articles(articles, filters) -> List[dict]`: pure function.
  - `from` / `to` (`YYYY-MM-DD`, inclusive) compare the date part of
    `published_date`. An article with no date is excluded only when a
    date filter is set.
  - `source_type`, `stakeholder`, `topic` (a `stable_topic_id`): exact
    match.
  - `q`: case-insensitive substring over `title` and `clean_content`.
    Matching articles get a `snippet`: about 80 characters either side
    of the first match, with `…` where the text was cut.
  - Sorted newest `published_date` first, undated last.
- `filter_options(articles) -> dict`: distinct non-null source types
  and stakeholders (sorted), topics as `[{id, label}]` sorted by label,
  and `date_min` / `date_max` over the whole corpus (not the filtered
  set, so options don't vanish while filtering).
- A reader built like `topic_counts.reader`: caches `read_corpus` for
  60 seconds in memory and turns a failed read into an unavailable
  result with a reason instead of raising. `reader_from_env()` returns
  an always-unavailable reader when Supabase is not configured.
- `search_comments(client, article_ids, q, limit=50)`: PostgREST
  `ilike` on `comments.body_text` with `%`, `_` and `\` escaped so they
  match literally, `in_("article_id", ids)`, newest `created_at` first,
  `count="exact"` for the total. Returns `[]` without a query when
  `article_ids` is empty. Each comment gets a snippet the same way
  articles do, and its article's title.

`topic_counts.top_topics()` is reused to count the filtered articles'
topics. Its input rows already have the `stable_topic_id` / `topic`
keys it reads. This changes what "unassigned" means on the dashboard:
today it is topic rows with no stable ID; now it is analysable articles
with no topic. When the filters leave no articles, the facet is
unavailable with the reason `No articles match these filters.`

### Endpoints

**`GET /api/v1/results`**, all query params optional, one value each:
`from`, `to`, `source_type`, `stakeholder`, `topic`, `q`.

```json
{
  "sentiment_distribution": {"positive": 0.55, "neutral": 0.23, "negative": 0.22},
  "top_topics": {"available": true, "reason": null, "counted": 120, "unassigned": 208, "items": [{"label": "...", "count": 31}]},
  "articles": {
    "available": true,
    "reason": null,
    "total": 41,
    "corpus": 328,
    "items": [{"id": 747, "title": "...", "url": "...", "source": "eSchool News",
               "published_date": "2026-08-17T10:00:00+00:00", "source_type": "trade_publication",
               "stakeholder": "educators", "stable_topic_id": "T004", "topic": "...", "snippet": null}]
  },
  "filter_options": {"source_types": [], "stakeholders": [], "topics": [{"id": "T004", "label": "..."}],
                     "date_min": "2025-01-03", "date_max": "2026-10-07"}
}
```

- `sentiment_distribution` is unchanged (hardcoded placeholder).
- `clean_content` never leaves the backend.
- Corpus unavailable (no Supabase, failed read): `articles.available`
  is `false` with a reason, `items` empty, totals 0, `top_topics`
  unavailable with the same reason, `filter_options` lists empty.
  Status stays 200, so the rest of the page loads.
- Bad `from` / `to` (not `YYYY-MM-DD`), `from` after `to`, or `q`
  outside 2–100 characters after trimming: 400 `{error}`.

**`GET /api/v1/search/comments`**, same params; `q` required.

```json
{"available": true, "reason": null, "total": 212,
 "comments": [{"comment_id": "...", "article_id": 747, "article_title": "...",
               "created_at": "...", "recommendation_count": 4, "snippet": "..."}]}
```

At most 50 comments; `total` is the full match count. Same 400 rules;
same unavailable shape (`comments` empty) when the corpus or the
comments read fails.

### Wiring

`create_app(runner=None, read_corpus=None, search_comments=None)`
replaces the `read_topics` parameter: `/results` no longer calls
`topic_counts.reader`. `tests/helpers.build_client` and the tests that
passed `read_topics` move to injecting a corpus reader. The live topic
count this replaces is the one the aggregation plan's Task 7 was going
to replace; that task now replaces this instead.

`run_dev_server.py` gets the unavailable reader (no Supabase), so the
dashboard shows the reason rather than data. Run `python app.py` with
`backend/.env` to see real data; its GET endpoints only read.

## Frontend

### State and API (owned by workstream A)

- `apiClient.getResults(filters)` and `apiClient.searchComments(filters)`
  serialise non-empty filter values as query params.
- `ViewStateContext` adds `filters` (`{from, to, source_type,
  stakeholder, topic, q}`, all `""` by default), `setFilters(patch)`
  (merges), `clearFilters()`, and `commentResults` / `commentsLoading`.
- The provider loads results itself whenever `filters` changes,
  including on mount, and loads comments when `filters.q` is non-empty
  (clears them otherwise). Components no longer call `loadResults()`;
  `DashboardShell`'s mount effect goes.
- A response that arrives after a newer request was made is dropped,
  so fast filter changes can't show stale results.

### Components (owned by workstream A, new files)

Each reads the view state itself and takes no props, like
`AdminConsole`.

- `FilterPanel.jsx`: date from / to (`<input type="date">`, bounded by
  `date_min` / `date_max`); source type, stakeholder and topic
  `<select>`s with an "All" option; a search `<input type="search">`
  that applies on Enter (in a `<form>`); a "Clear filters" button. Every
  control has a `<label>`. Codes display as words: `trade_publication`
  → "Trade publication".
- `ArticleTable.jsx`: "Showing 41 of 328 articles"; columns title
  (link to `url`, new tab), date, source, source type, stakeholder,
  topic. When searching, the snippet shows under the title with the
  match wrapped in `<mark>`. Empty states: unavailable reason, or "No
  articles match these filters." No sentiment column: a per-row value
  would be invented.
- `CommentResults.jsx`: rendered only while `filters.q` is set. "212
  comments mention “…” (showing 50)", then each comment's snippet (match
  in `<mark>`), its article title, date and recommendation count.

They use plain semantic HTML (`form`, `label`, `select`, `input`,
`button`, `table`, `ul`, `mark`) and these class names, which workstream
B styles: `filter-panel`, `field`, `field-row`, `table-meta`,
`data-table`, `snippet`, `comment-list`, `comment`, `comment-meta`,
`empty-note`.

### Redesign (owned by workstream B)

- `frontend/src/styles.css` (new), imported once in `main.jsx`. Tokens
  on `:root`: the colours from `statusStyles.js` (which keeps exporting
  its JS objects for the charts and badges), a neutral surface and text
  scale, spacing, radius, shadow and a type scale. System font stack.
- Layout in `DashboardShell`:
  - Top bar: "ClassroomScope", a short tagline, and two tabs,
    **Dashboard** and **Pipeline runs** (buttons with `aria-pressed` or
    a `role="tablist"`, local state, no router).
  - Dashboard: a ~280px sticky sidebar holding `<FilterPanel />`; a main
    column with Sentiment and Top topics as side-by-side cards, then an
    Articles card (`<ArticleTable />`), then `<CommentResults />` as its
    own card. Below 900px the sidebar stacks above the main column.
  - Pipeline runs: `<AdminConsole />`, restyled.
- Inline `style={{…}}` props in `DashboardShell`, `AdminConsole`,
  `StatusBadge`, and the chart wrappers in `VisualizationViews` move to
  classes, except values computed from data (badge colours).
- Styles the class names listed under Components, plus base styles for
  `table`, form controls, `button`, `mark`, focus rings and the
  placeholder note.
- Accessibility: visible focus on every control, text contrast at least
  4.5:1, status always carried by text as well as colour.

### File ownership

| Workstream | Owns |
|---|---|
| A: filters + search | `backend/orchestrator/corpus.py`, `backend/app.py`, `backend/run_dev_server.py`, `backend/tests/*`, `frontend/src/api/apiClient.js`, `frontend/src/state/ViewStateContext.jsx`, `frontend/src/components/{FilterPanel,ArticleTable,CommentResults}.jsx` |
| B: redesign | `frontend/src/styles.css`, `frontend/src/main.jsx`, `frontend/src/App.jsx`, `frontend/src/components/{DashboardShell,AdminConsole,StatusBadge,VisualizationViews}.jsx`, `frontend/src/components/statusStyles.js` |
| Coordinator (merge) | `README.md`, `NEXT_STEPS.md`, final wiring fixes |

Before either workstream starts, the coordinator commits the three
workstream-A components as minimal stubs that render their class name
and a "coming soon" line, so workstream B can import and lay them out
while A fills them in. B never edits those three files.

## MVP shortcuts (go into the README)

| Shortcut | Ceiling | Better version |
|---|---|---|
| Corpus read from 4 tables and filtered in Python per request, 60s cache | Slows as the corpus grows; up to 60s stale after a run | Aggregation snapshot or a Postgres view/RPC |
| Single-select filters | Can't compare two stakeholders | Multi-select |
| Substring search, first match only | No ranking, stemming or phrase logic | Postgres full-text search (`tsvector`) with ranking |
| Comment search capped at 50, no paging | Can't browse all matches | Paging or infinite scroll |
| No pagination on articles | Fine at hundreds, not thousands | Server-side paging |
| Filters not in the URL | A filtered view can't be shared or bookmarked | Sync filters to query string |
| Classification merge: non-baseline beats baseline | Hides disagreement between classifiers | Record a chosen classifier per article in the pipeline |
| Sentiment donut is a hardcoded placeholder | Not real data | Aggregate `sentiment_results` once the agent is wired |
| No frontend tests | Regressions caught by eye | Vitest + Testing Library |

## Verification

- Backend: `pytest` from `backend/`, whole suite green. New tests use
  fake clients (as `test_topic_counts.py` does) for the merge rules,
  filters, snippets, escaping, the unavailable paths and both routes.
- Frontend: `npm run build` succeeds.
- In the browser: `python app.py` (real data, GETs only) plus
  `npm run dev`, rendered in headless Edge with
  `--force-prefers-reduced-motion` so charts draw. Check: 328 articles
  unfiltered; a stakeholder filter changes both the chart and the
  count; a search shows snippets and comments; the Pipeline runs tab
  lists runs (don't start one: with `app.py` that runs the real
  agents); layout holds at 375px and 1280px.
