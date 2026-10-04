# ClassroomScope (in progress)

**Status:** front-end skeleton confirmed working end-to-end, and the
backend pipeline coordinator's groundwork is in place (see
[Pipeline coordinator](#pipeline-coordinator-in-progress) below).
The front end is not complete — it's the minimum wiring needed to prove the
three-layer architecture from the design doc actually connects, before
building out the real views.

## What's working right now

- Flask backend (`backend/app.py`) serving two endpoints:
  - `GET /api/v1/health` — reachability check
  - `GET /api/v1/results` — stub data shaped like what the real
    Aggregation Service will eventually return
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

- FilterPanel, real charts (VisualizationViews), ExportControls,
  AdminConsole — see design doc Section 2 for what each needs to do
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
  source type) and topic (a saved BERTopic model, whose file is restored
  by hand; where it is missing, topic stays a stub). Sentiment exists as
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
2. Swap the plain HTML list/table for a real charting library
3. Connect apiClient to the real Data Access Layer once SS-1/SS-2/SS-3
   are integrated (see WBS, tasks under 4.5)
4. Add auth context once SS-5 login exists

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
2. **VisualizationViews** — replace the plain sentiment
   breakdown/article list in `DashboardShell.jsx` with real charts.
   Pick a charting library as a team before splitting up chart types.
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
