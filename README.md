# ClassroomScope (in progress)

> **Branch `dashboard-mvp-filters`: workstream A of the dashboard MVP. Not started (2026-10-08).**
>
> Builds features 1 and 2 of the MVP. Both are MVP: they work, but take
> known shortcuts we'll come back to.
>
> - **Filter panel.** The article table lists the 328 analysable articles
>   instead of two made-up rows. Filters for date range, source type,
>   stakeholder and topic update both the topic chart and the table.
> - **Keyword search.** One search box searches article titles and text
>   and the 29,658 article comments, with a snippet around each match.
>
> This branch owns these files, and nothing else:
>
> - Backend: `backend/orchestrator/corpus.py` (new), `backend/app.py`,
>   `backend/run_dev_server.py`, `backend/orchestrator/topic_counts.py`,
>   and `backend/tests/*`.
> - Frontend: `frontend/src/api/apiClient.js`,
>   `frontend/src/state/ViewStateContext.jsx`, and the new
>   `FilterPanel.jsx`, `ArticleTable.jsx`, `CommentResults.jsx` and
>   `text.jsx` in `frontend/src/components/`.
>
> Its dev servers run on ports 5001 (backend) and 5174 (Vite).
>
> - Plan: `docs/superpowers/plans/2026-10-08-dashboard-mvp.md`, Tasks A1–A6
>   (written, **not yet approved**)
> - Spec: `docs/superpowers/specs/2026-10-08-dashboard-filters-redesign-design.md`
> - The plan's backend code already passed in a scratch copy: 150 tests,
>   plus a read-only check against the real database (328 articles; 82
>   comments mention "cheating").
>
> **To resume:**
>
> 1. Approve the plan.
> 2. Wait for Task 0 on `dashboard-mvp`, then run `git merge dashboard-mvp`
>    here.
> 3. Hand Tasks A1–A6 to a subagent working in this worktree
>    (`../ClassroomScope-mvp-filters`).
>
> This branch merges back into `dashboard-mvp`, not `main`. Delete this
> note at that merge.

**Status:** front-end skeleton confirmed working end-to-end, and the
backend pipeline coordinator's groundwork is in place (see
[Pipeline coordinator](#pipeline-coordinator-in-progress) below).
The front end is not complete — it's the minimum wiring needed to prove the
three-layer architecture from the design doc actually connects, before
building out the real views.

## What's working right now

- Flask backend (`backend/app.py`) serving two endpoints:
  - `GET /api/v1/health` — reachability check
  - `GET /api/v1/results` — topic counts read live from
    `topic_results`; the sentiment and article parts are still stub
    data shaped like what the real Aggregation Service will return
- React front end (`frontend/`) with the three layers from the design
  doc partially built:
  - **Data access layer** (`src/api/apiClient.js`) — the single client
    that talks to Flask
  - **State layer** (`src/state/ViewStateContext.jsx`) — holds results,
    loading, and error state
  - **Presentation layer** (`src/components/DashboardShell.jsx`) — one
    view, rendering sentiment breakdown and an article list pulled
    live from the Flask stub
- Verified end to end: `npm run dev` + `python app.py` together produce
  a page that fetches real JSON from Flask and renders it. No mock data
  baked into the front end.

## What's NOT built yet

- FilterPanel and ExportControls — see design doc Section 2 for what
  each needs to do
- Auth / session context (SS-5 login) — apiClient has TODOs where the
  token will attach
- Run-status poller
- Real data — everything above is served from a hardcoded stub in
  `app.py`, not the actual Core Database

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
python -m pytest tests agents/topic      # run the test suite (98 tests)
python -m pyright backend/               # type check (from the repo root)
```

**Front end** (separate terminal)
```
cd frontend
npm install
npm run dev             # serves http://localhost:5173
```

Open `http://localhost:5173` — you should see live data pulled from
the Flask stub, not placeholder text.

## Next steps (planned)

1. Build FilterPanel and wire it into ViewStateContext
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

**Components to design and build** (currently missing from
`frontend/src/components/`):

1. **FilterPanel** — controls for narrowing the results shown in
   `DashboardShell`. Should read/write filter state via
   `ViewStateContext.jsx` rather than owning its own state.
2. **VisualizationViews** — built (`VisualizationViews.jsx`, using
   Recharts): a sentiment donut and a top-topics bar chart. New chart
   types should use Recharts too. The article list stays a table: a
   chart of a handful of rows would present a sample as a distribution.
3. **ExportControls** — UI for exporting the current view/results
   (format TBD — propose an approach if it's not obvious from the
   design doc).
4. **AdminConsole** — a separate view/route, not part of the main
   dashboard; scope it small for now (whatever the design doc
   describes as minimum viable).

**Guidelines while doing this:**

- Follow the three-layer split already established (data access /
  state / presentation) — don't reach into `apiClient.js` directly
  from a new component.
- No new mock data — everything should render from the existing Flask
  stub (`backend/app.py`) or explicitly note where the stub is missing
  a field you need, so we can add it.
- Keep PRs scoped to one component at a time so they're easy to
  review.
- If a component's requirements are ambiguous, check the design doc
  (Section 2) first; if still unclear, flag it rather than guessing.

**Not in scope this week:** auth/login (SS-5), the run-status poller,
or connecting to the real Aggregation Service/Core Database — those
come later per the steps above.
