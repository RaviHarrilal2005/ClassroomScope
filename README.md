# ClassroomScope (in progress)

**Status:** front-end skeleton confirmed working end-to-end, and the
backend pipeline coordinator's groundwork is in place (see
[Pipeline coordinator](#pipeline-coordinator-in-progress) below).
The front end is not complete — it's the minimum wiring needed to prove the
three-layer architecture from the design doc actually connects, before
building out the real views.

## What's working right now

- Flask backend (`backend/app.py`) serving the dashboard:
  - `GET /api/v1/health` — reachability check
  - `GET /api/v1/results` — the analysable articles (328 on 2026-10-11) and their topic
    counts, narrowed by `from`, `to`, `source_type`, `stakeholder`,
    `topic` and `q` (`orchestrator/corpus.py`). Sentiment is still a
    hardcoded placeholder
  - `GET /api/v1/search/comments` — keyword search over the article
    comments, on the articles the other filters allow
- React front end (`frontend/`) with the three layers from the design
  doc partially built:
  - **Data access layer** (`src/api/apiClient.js`) — the single client
    that talks to Flask
  - **State layer** (`src/state/ViewStateContext.jsx`) — holds results,
    loading, and error state
  - **Presentation layer** (`src/components/`) — a Dashboard tab
    (filter panel, sentiment and topic charts, article table, comment
    search) and a Pipeline runs tab, styled from `src/styles.css`
- Verified end to end: `npm run dev` + `python app.py` together produce
  a page that fetches real JSON from Flask and renders it. No mock data
  baked into the front end.

## What's NOT built yet

- ExportControls — see design doc Section 2 for what it needs to do
- Auth / session context (SS-5 login) — apiClient has TODOs where the
  token will attach
- Real sentiment figures — the donut is still a hardcoded placeholder
  in `app.py` (see the MVP table below)

## Pipeline coordinator (in progress)

`backend/orchestrator/` runs the agents in order —
**Collection → Security → Analysis (4 agents at once) → Aggregation** —
and records each stage's status. It retries collection, skips analysis
if security screening fails, uses a fallback when sentiment fails, and
keeps the results of stages that succeeded when another fails.

- **Four of the seven agents are real**: collection (news APIs + RSS,
  dedupe, keyword then LLM relevance check, body extraction), security
  (content sanitization screening), classification (stakeholder and
  source type) and topic (a saved BERTopic model, stored in the repo with
  Git LFS; where it is missing, topic stays a stub). Sentiment exists as
  a standalone script that is not wired in
  yet; stance and aggregation have no implementation. Each owner's code
  lives in `backend/agents/<stage>/`.
- The registry picks real agents when Supabase is configured and stubs
  otherwise, so the app and the tests still work without credentials.
- Run status is written to **Supabase** (`pipeline_runs` /
  `pipeline_stage_runs`) when `SUPABASE_URL` and `SUPABASE_KEY` are set,
  and kept in memory otherwise, so the app still starts without
  credentials. Every store method is verified against the real database.
- Verified end to end against the real database: a full run over 40 real
  articles records all seven stages, finishing `completed`. Note
  `POST /api/v1/runs` returns
  `202` straight away and the pipeline continues on a background thread,
  so polling immediately shows `running` with stages still `pending` —
  that is normal, not a stall.
- Endpoints: `POST /api/v1/runs`, `GET /api/v1/runs`, `GET /api/v1/runs/<id>`

Full details, the agent contract, and open questions:
[`docs/pipeline-coordinator.md`](docs/pipeline-coordinator.md)

## Running it

**Backend**
```
cd backend
pip install -r requirements.txt
cp .env.example .env      # then fill in SUPABASE_KEY
python app.py             # serves http://localhost:5000
```

The topic model (441 MB) is stored with [Git LFS](https://git-lfs.com).
Install it before cloning or pulling, or run `git lfs pull` afterwards;
without it you get a small pointer file and topic stays a stub.

`backend/.env` holds the credentials; it is gitignored and must never be
committed. `SUPABASE_URL` must be the **API endpoint**
(`https://<ref>.supabase.co`), not the dashboard page, and `SUPABASE_KEY`
should be the **secret** (`sb_secret_…`) key — the publishable key has no
write access to the run tables. Without a `.env` the backend still runs,
but keeps run status in memory only.

The news-API keys in `.env.example` are optional: a source with no real
key is skipped, and an unfilled placeholder counts as no key. The
`TRUSSED_*` LLM keys are needed to collect new articles, since an
article is only kept once the LLM confirms it is relevant; without them
a live collection run fails up front, and classification falls back to
its keyword scorer. `--backlog` runs need neither.

**Pipeline demo and tests** (from `backend`)
```
pip install -r requirements-dev.txt
python run_pipeline.py                   # run once with stubs, print each stage
python run_pipeline.py --fail topic      # see how a failing agent is handled
python run_pipeline.py --live --backlog  # the real agents, over articles already
                                         # stored (no API quota, no downloads)
python -m pytest                        # the offline test suite (172 tests)
python -m pyright backend/               # type check (from the repo root)
```

**End-to-end checks** (from `backend`; these write to the Supabase
project in `.env`)
```
pip install -r requirements-dev.txt
python -m playwright install chromium    # once per machine, about 150 MB
python -m pytest e2e                     # real pipeline over 5 stored articles,
                                         # the API, and the dashboard in Chromium
python -m pytest e2e --collect           # plus one real RSS + GNews collection
```
Each session writes `backend/e2e/results/<date-time>/results.md` with the
screenshots. `E2E_ENV_FILE=<file>` points the suite at another database;
the first lines of the output name the database in use.
The latest report: [docs/testing/e2e-test-report.md](docs/testing/e2e-test-report.md).

**Front end** (separate terminal)
```
cd frontend
npm install
npm run dev             # serves http://localhost:5173
```

Open `http://localhost:5173` with `python app.py` running — you should
see the real articles and topic counts from the database, not
placeholder text. (`run_dev_server.py` reads no database, so its
article table is empty.)

## MVP features — come back to these

The filter panel, keyword search and visual redesign (October 2026) are
MVPs: they work end to end, but each takes shortcuts on purpose. Design:
`docs/superpowers/specs/2026-10-08-dashboard-filters-redesign-design.md`.

| Feature | Shortcut | Ceiling | Better version |
|---|---|---|---|
| Filters | Corpus read from 3 tables and filtered in Python per request, behind a 60s cache (`orchestrator/corpus.py`) | Slows as the corpus grows; up to 60s stale after a run | Aggregation snapshot or a Postgres view/RPC |
| Filters | One value per filter | Can't compare two stakeholders | Multi-select |
| Filters | Not kept in the URL; nor is the Dashboard / Pipeline runs tab | A filtered view can't be shared, bookmarked or survive a refresh | Sync filters and view to the query string |
| Filters | Topic options are the full list, not narrowed by the other filters | Some combinations give zero rows | Facet counts per option |
| Filters | Classification merge: any classifier beats `baseline_keyword` | Hides disagreement between classifiers | Record a chosen classifier per article in the pipeline |
| Filters | A request per filter change, no debounce or cancel (stale responses are dropped, not aborted) | Wasted requests while typing a date | Debounce dates; `AbortController` |
| Article table | Every match rendered, no paging | Fine at hundreds, not thousands | Server-side paging |
| Search | Case-insensitive substring, first match only | No ranking, stemming or phrases | Postgres full-text search (`tsvector`) with ranking |
| Search | `*` acts as a wildcard (PostgREST has no escape for it) | `a*b` matches more than it says | Search through an RPC function |
| Search | Comment search capped at the newest 50, no paging; article IDs sent in the URL | Can't browse all matches; breaks past ~1,500 articles | Paging, and an RPC taking the filters |
| Dashboard | Sentiment donut is a hardcoded placeholder | Not real data, and filters don't move it | Aggregate `sentiment_results` once the agent is wired in |
| Redesign | Light theme only; badge colours inline in `StatusBadge` | Ignores an OS dark-mode preference | `prefers-color-scheme` token set, badge colours as tokens |
| Redesign | Topic chart labels wrap to two lines at most | Labels over ~56 characters clip | Measure text, or wrap to N lines |
| Pipeline runs | All 20 recent runs listed; Start a run has no confirm step | Long list on phones; one click runs the real pipeline | Cap the list; confirm step, admin-only (TODO(auth)) |
| Frontend | No frontend tests | Regressions caught by eye | Vitest + Testing Library |
| End-to-end checks (`backend/e2e`) | Run against the team's shared Supabase project: 5 stored articles per run, real collection only with `--collect` | Every run writes to team data: run history, re-written classifications, sometimes new articles | A separate test database, selected with `E2E_ENV_FILE=.env.test` |
| End-to-end checks (`backend/e2e`) | Dashboard checks find elements by their visible text and layout | A redesign that changes that text breaks D1–D3, and the October redesign did: D1 fails today, D2 and D3 are untested against it | `data-testid` attributes on the elements the tests use |

## Next steps (planned)

1. Work through the MVP table above
2. Connect apiClient to the real Data Access Layer once SS-1/SS-2/SS-3
   are integrated (see WBS, tasks under 4.5)
3. Add auth context once SS-5 login exists

## This week: initial site design refinement

The skeleton above is functionally wired but visually bare — this
week's focus is designing and building out the views that don't exist
yet, not touching backend/data logic. Everything reads live data
already flowing through `apiClient.js` → `ViewStateContext.jsx` →
`DashboardShell.jsx`; new components should plug into that same state
layer rather than fetching independently.

**Components in `frontend/src/components/`** (all built except
ExportControls):

1. **FilterPanel** — built (MVP, see the table above): date range,
   source type, stakeholder, topic and keyword search, with filter
   state in `ViewStateContext.jsx`.
2. **VisualizationViews** — built (`VisualizationViews.jsx`, using
   Recharts): a sentiment donut and a top-topics bar chart. New chart
   types should use Recharts too. The article list stays a table: a
   chart of a handful of rows would present a sample as a distribution.
3. **ExportControls** — UI for exporting the current view/results
   (format TBD — propose an approach if it's not obvious from the
   design doc).
4. **AdminConsole** — built: the "Pipeline runs" tab, separate from
   the main dashboard.

**Guidelines while doing this:**

- Follow the three-layer split already established (data access /
  state / presentation) — don't reach into `apiClient.js` directly
  from a new component.
- No new mock data — everything should render from the Flask backend
  (`backend/app.py`) or explicitly note where it is missing a field you
  need, so we can add it.
- Keep PRs scoped to one component at a time so they're easy to
  review.
- If a component's requirements are ambiguous, check the design doc
  (Section 2) first; if still unclear, flag it rather than guessing.

**Not in scope this week:** auth/login (SS-5)
or connecting to the real Aggregation Service/Core Database — those
come later per the steps above.
