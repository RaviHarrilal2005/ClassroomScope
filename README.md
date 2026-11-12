# ClassroomScope (in progress)

**Status:** the dashboard and the pipeline run end to end, with a real agent
at every stage (see [Pipeline coordinator](#pipeline-coordinator) below).
What remains, and how to check each part, is in
[NEXT_STEPS.md](NEXT_STEPS.md); the known shortcuts are in the MVP table.

## What's working right now

- Flask backend (`backend/app.py`) serving the dashboard:
  - `GET /api/v1/health` — reachability check
  - `GET /api/v1/results` — the analysable articles and their topic
    counts, narrowed by `from`, `to`, `source_type`, `stakeholder`,
    `topic` and `q` (`orchestrator/corpus.py`), with the sentiment
    figures (the share, and by month, topic and stakeholder), the stance
    and the reader-comment sentiment for the same articles
    (`agents/aggregation/`)
  - `GET /api/v1/search/comments` — keyword search over the article
    comments, on the articles the other filters allow
  - the pipeline endpoints (`orchestrator/routes.py`), listed below
- React front end (`frontend/`), in three layers:
  - **Data access layer** (`src/api/apiClient.js`) — the single client
    that talks to Flask
  - **State layer** (`src/state/ViewStateContext.jsx`) — holds the
    filters, the open tab, results, loading, and error state. The filters
    and tab are mirrored in the URL, so a filtered view can be shared
    (`src/urlState.js`)
  - **Presentation layer** (`src/components/`), styled from
    `src/styles.css`, with the dark theme following the OS setting:
    - Dashboard tab: filter panel, a headline naming the most negative
      stakeholder and topic, sentiment donut, stance donut, the
      "How readers react" donut (reader comments), top-topics bar,
      "Sentiment by month" chart, sentiment split bars by stakeholder and
      by topic, article table (with a stance column and Export CSV), and
      comment search
    - Pipeline runs tab (`AdminConsole.jsx`)
- Verified end to end: `npm run dev` + `python app.py` together produce
  a page that fetches real JSON from Flask and renders it. No mock data
  baked into the front end.

## Pipeline coordinator

`backend/orchestrator/` runs the agents in order —
**Collection → Security → Analysis (5 agents at once) → Aggregation** —
and records each stage's status. It retries collection, skips analysis
if security screening fails, uses a fallback when sentiment fails, and
keeps the results of stages that succeeded when another fails.

- **Every stage has a real agent**: collection (news APIs + RSS,
  dedupe, keyword then LLM relevance check, body extraction), security
  (content sanitization screening, of articles and reader comments),
  classification (stakeholder and source type) and topic (a saved
  BERTopic model, stored in the repo with Git LFS; where it is missing,
  topic stays a stub). Sentiment (RoBERTa, with VADER as its fallback)
  and comment sentiment (a 3-class RoBERTa over the screened reader
  comments) run where `transformers` and `vaderSentiment` are installed.
  Stance (whether an article is for, against or neutral toward GAI in
  education, labelled by the Luna LLM) runs where `TRUSSED_API_KEY` is
  set. Aggregation computes the dashboard's figures. Each owner's code
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
python -m pytest                        # the offline test suite
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
npm test                # the CSV, URL state and month tests (Node's built-in runner)
```

Open `http://localhost:5173` with `python app.py` running — you should
see the real articles and topic counts from the database, not
placeholder text. (`run_dev_server.py` reads no database, so its
article table is empty.) To point the front end at a backend on another
port, set `VITE_API_URL` before `npm run dev`; it must end in `/api/v1`
(the default is `http://localhost:5000/api/v1`).

## MVP features — come back to these

The filter panel, keyword search and visual redesign (October 2026) are
MVPs: they work end to end, but each takes shortcuts on purpose. Design:
`docs/superpowers/specs/2026-10-08-dashboard-filters-redesign-design.md`.

| Feature | Shortcut | Ceiling | Better version |
|---|---|---|---|
| Filters | Corpus read from 4 tables and filtered in Python per request, behind a 60s cache (`orchestrator/corpus.py`) | Slows as the corpus grows; up to 60s stale after a run | Aggregation snapshot or a Postgres view/RPC |
| Filters | One value per filter | Can't compare two stakeholders | Multi-select |
| Filters | Filters and tab kept in the URL with `replaceState`; the tabs are buttons, not links; other query params (utm_*) are dropped, and a source, stakeholder or topic in a shared link that the corpus lacks is cleared without a notice | Back doesn't undo a filter change; a tab can't be opened in a new browser tab; a stale link quietly shows a wider view than it names | `pushState` for deliberate changes; tabs as `<a href>`; a notice naming what was cleared |
| Filters | Topic options are the full list, not narrowed by the other filters | Some combinations give zero rows | Facet counts per option |
| Filters | Classification merge: any classifier beats `baseline_keyword` | Hides disagreement between classifiers | Record a chosen classifier per article in the pipeline |
| Article table | Every match rendered, no paging | Fine at hundreds, not thousands | Server-side paging |
| Search | Case-insensitive substring, first match only | No ranking, stemming or phrases | Postgres full-text search (`tsvector`) with ranking |
| Search | `*` acts as a wildcard (PostgREST has no escape for it) | `a*b` matches more than it says | Search through an RPC function |
| Search | Comment search capped at the newest 50, no paging; article IDs sent in the URL | Can't browse all matches; breaks past ~1,500 articles | Paging, and an RPC taking the filters |
| Aggregation | Sentiment figures recomputed from the cached corpus on every request; the pipeline stage checks they can be computed and stores nothing (`agents/aggregation/`) | No record of the figures per run, so runs can't be compared over time | A snapshot row per run |
| Sentiment charts | Headline names a group or topic only at 20+ articles, a fixed cutoff (`MIN_ARTICLES_TO_NAME`, in `compute.py` and `VisualizationViews.jsx`) | Not a significance test: at 20 one article still moves a share 5 points | A confidence interval per share, named only when it clears the overall figure |
| Sentiment charts | Sentiment by month: a 100% column per calendar month, months with no articles kept as empty columns; wider than its card (about 20+ months, on any screen), it scrolls sideways and opens at the newest month | One old article adds an empty column for every month since; the % axis scrolls out of view; 32 months of data today fill 49 columns, so the date filter is the way to zoom | Bin by week or quarter to suit the date range; drop isolated old months |
| Stance | One LLM call per article, never checked against human labels; the confidence is the model's own and is about 0.95 on nearly every article | Accuracy is unknown, and confidence can't separate sure labels from unsure ones | Hand-label a sample (say 50 articles) and report agreement (Cohen's kappa); drop or calibrate the confidence |
| Stance | The article as a whole toward one target, "generative AI in education" | An article for AI tutoring but against AI essays gets one label | Stance per aspect; `stance_results.target` already holds the target per row |
| Reader comments | Every comment counts once, pooled over the filtered articles | The few most-discussed articles set the share | Average per article, or show the spread |
| Reader comments | Only articles from sources that publish comments have any | "How readers react" covers a narrow slice of the coverage | More comment sources (Supabase already has Reddit tables) |
| Sentiment charts | Hover tooltips on the monthly and topic charts only, by mouse or touch; none on the donuts, which print every value | No tooltip by keyboard (`accessibilityLayer` is off); keyboard and screen-reader users get the printed values and the "Month by month" list | Recharts' `accessibilityLayer` once its `role="application"` stops hiding the printed labels from screen readers |
| Redesign | Dark theme follows the OS setting only (`prefers-color-scheme` in `styles.css`) | No way to pick light or dark per site | A toggle that sets `data-theme` on `<html>` and is remembered |
| Redesign | Topic chart labels wrap to two lines at most | Labels over ~56 characters clip | Measure text, or wrap to N lines |
| Pipeline runs | All 20 recent runs listed; Start a run and Run on 5 stored articles have no confirm step, so anyone who can reach the app can start a real run | Long list on phones; one click runs the real pipeline | Cap the list; a confirm step, or limit runs to local use |
| Pipeline runs | Run on stored articles always takes the 5 oldest analysis-ready articles (`BACKLOG_RUN_SIZE`) | Re-analyses the same 5 every time; can't pick which or how many | Take a size, or specific article IDs, in the request |
| Export | Article list only, the columns the table has; built in the browser | No full text, comments, per-classifier results, column picker, or other formats; nothing ties a file to a pipeline run | Each is an add-on with no schema change, except export-by-run (`run_id` on the results tables, open question 3 in `docs/pipeline-coordinator.md`) |
| Frontend | Only `src/csv.js` and `src/urlState.js` have tests (`npm test`, Node's built-in runner); no component tests | UI regressions caught by eye | Vitest + Testing Library |
| End-to-end checks (`backend/e2e`) | Run against the team's shared Supabase project: 5 stored articles per run, real collection only with `--collect` | Every run writes to team data: run history, re-written classifications, sometimes new articles | A separate test database, selected with `E2E_ENV_FILE=.env.test` |
| End-to-end checks (`backend/e2e`) | Dashboard checks find elements by their visible text and layout | A redesign that changes that text breaks D1–D3. The October redesign did, and they were rewritten for it | `data-testid` attributes on the elements the tests use |

## Where things stand

The dashboard and the pipeline are built as described above. What is left,
and how to tell when each part is done, is in [NEXT_STEPS.md](NEXT_STEPS.md).
The known shortcuts, and what would replace each, are the MVP table.

**Guidelines for front-end work:**

- Follow the three-layer split already established (data access /
  state / presentation) — don't reach into `apiClient.js` directly
  from a new component.
- No new mock data — everything should render from the Flask backend
  (`backend/app.py`) or explicitly note where it is missing a field you
  need, so we can add it.
- New charts use Recharts. Sentiment is blue / light grey / red (red and
  green blur together for red-green colour blindness), and the article
  list stays a table.
- Keep PRs scoped to one component at a time so they're easy to
  review.
- If a component's requirements are ambiguous, check the design docs in
  `docs/superpowers/specs/` first; if still unclear, flag it rather than
  guessing.

**Dropped from scope (2026-11-08):** auth/login (SS-5), by the professors
and sponsors.
