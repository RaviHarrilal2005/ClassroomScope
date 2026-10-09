# End-to-end testing of the integrated pipeline — design

**Date:** 2026-10-08
**Status:** approved in conversation, awaiting review of this written spec
**Owner:** Ravi (WBS: "Lead end-to-end testing of the complete integrated pipeline")

## Goal

Two deliverables:

1. **A repeatable end-to-end check.** One command runs the real pipeline,
   calls every API endpoint, drives the dashboard in a real browser, and
   prints pass or fail for each check. It can be rerun whenever something
   changes, and it is rerun at the end of the filter panel and redesign
   work that follows.
2. **A written test report** for the team and the instructor: what was
   tested, the results, the problems found, and recommendations. It is
   written from one full run of the check.

Today nothing tests the system end to end. The 111 offline tests on main
use stubs and fakes, never touch the network, and the frontend has no
tests at all.

## Decisions taken

| Question | Decision |
|---|---|
| What to produce | Both an automated check and a written report. |
| Database | The team's shared Supabase project, for now. Routine runs analyse **stored articles only**; an opt-in flag adds one real collection run. A separate test database comes later, and the design must make switching to it a configuration change. |
| Tooling | pytest plus Playwright for Python, in one suite and one command. |

## Scope

**In scope:** collection (stored-article mode, and real collection behind a
flag), security, classification, topic, the stub stages as they run today,
the run and results API, the dashboard and the admin console.

**Out of scope:** what the stub agents (sentiment, stance, aggregation)
would do once built; Guardian sources and comments, which are not wired
into runs; a separate test database (later); running in CI, which would
need the team's secrets; load, performance and cross-browser testing.

## How the suite runs

### Location and invocation

- New folder `backend/e2e/`, with its own `conftest.py`, separate from
  `backend/tests/`.
- New `backend/pytest.ini` with `testpaths = tests agents/topic`. Without
  it, a plain `pytest` collects every test file under `backend/`, which
  would start writing to the shared database by accident. With it, plain
  `pytest` behaves exactly as today.
- The suite runs only when named, from `backend/`:
  - `python -m pytest e2e`: routine run, stored articles only.
  - `python -m pytest e2e --collect`: also runs a real collection (tests
    C1–C2 below).
- Prerequisites, listed in the README:
  `pip install -r requirements-dev.txt` (adds `pytest-playwright`), a
  one-time `python -m playwright install chromium` (about 150 MB),
  `npm install` in `frontend/`, Git LFS with the topic model pulled, and a
  `backend/.env` with Supabase credentials (and `TRUSSED_*` for
  `--collect`).

### Database and credentials

- Credentials come from `backend/.env`, as the app's do.
- `E2E_ENV_FILE=<path>` names another file whose values win over
  `backend/.env`. It is loaded with override before the app or any agent
  is imported. This is how the future test database plugs in: a different
  file, no code change.
- If Supabase is not configured, the session stops at once with one
  message rather than failing test by test.
- The start of every run prints, and the results record, the database
  host (never the key).

### Servers, started inside the test session

- **Backend.** The real Flask app from `create_app(...)`, served from a
  thread on a free port. Its runner uses the real agents, but its
  collection stage is wired to **stored articles only, 5 per run**
  (`build_default_registry(live=True, backlog=True, backlog_limit=5)`)
  with the Supabase run store. A "Start a run" click during the tests can
  therefore never set off a live collection. The topic counts reader is
  the app's default (live from `topic_results`).
- **Collection run (`--collect` only).** Run directly through
  `PipelineCoordinator` with `build_default_registry(live=True,
  sources=["rss", "gnews"])` and the Supabase run store, not through the
  test server. NewsAPI is never used: one run can add around 1,800
  articles.
- **Frontend.** Built once per session with Vite into a temporary folder,
  with `VITE_API_BASE_URL` pointing at the test backend, and served by
  Python's built-in HTTP server from a thread on a free port. This tests
  the production build and cannot collide with dev servers on 5173 or
  5000.
- **App change this needs:** `frontend/src/api/apiClient.js` reads its
  base address from `import.meta.env.VITE_API_BASE_URL`, defaulting to
  today's `http://localhost:5000/api/v1`.
- **Browser.** Playwright's headless Chromium. Console messages and page
  errors are captured for every page.

## What it checks

The default run uses the same 5 stored articles each time: stored-article
mode takes the lowest-numbered analysable articles. Expected values come
from direct Supabase queries, never from the code under test.

### Setup checks (stop the session with a reason if they fail)

- **S1.** Supabase is reachable with the configured key: `pipeline_runs`
  can be read.
- **S2.** The topic model is real: the registry picks the real topic agent.
  If the model file is missing or a Git LFS pointer, topic would quietly
  be a stub, so this fails and says to run `git lfs pull`.
- **S3.** Records whether the LLM classifier or the keyword fallback is
  the primary classifier. Informational, never a failure.

### Pipeline, through the API (one shared run)

A session fixture starts one run with `POST /api/v1/runs`, immediately
sends a second `POST`, then polls `GET /api/v1/runs/<id>` until the run
finishes or 5 minutes pass. It records what it saw; tests P1–P5 assert on
those records.

- **P1.** The first `POST` returns 202 with the run `running` and all 7
  stages `pending`.
- **P2.** The run finishes `completed` within the time limit, every stage
  `succeeded`, 5 articles collected and 5 passed screening. Sentiment,
  stance and aggregation are asserted to have run, and the results mark
  them as stubs.
- **P3.** The second `POST` was refused with 409 and named the active run.
- **P4.** `GET /api/v1/runs` lists the new run first, and `active_run_id`
  is null after it finishes.
- **P5.** The database holds the results, checked directly in Supabase:
  the run and its 7 stage rows with their final statuses; classification
  rows written during the run covering exactly 5 analysable articles; a
  `topic_results` row for each of those 5 that is eligible (inserted now
  or kept from before).

### Results API

- **R1.** `GET /api/v1/results` returns topic counts equal to Supabase's
  own exact count per `stable_topic_id`, plus the unassigned count.

### Dashboard, in Chromium

- **D1.** The page loads with no console errors or page errors. Both
  charts draw; the topic bars match R1's counts in order; no chart label
  is cut off by its chart's edge; the sentiment and article sections still
  carry their placeholder notes.
- **D2.** The admin console's run history shows P2's run as completed.
- **D3.** Clicking "Start a run" runs the pipeline: the button disables,
  the stage table moves from running to succeeded, and the run finishes
  `completed`. Screenshots are taken while it runs and after.

### Real collection (`--collect` only)

- **C1.** A collection run from RSS and GNews finishes `completed`. Either
  it found new articles, or it reports "No new articles were collected".
  Both pass; the results record which, and the IDs of any new articles.
- **C2.** Every article C1 reports is stored with `llm_relevant = true`
  and `processing_status = 'success'`, and has classification rows.

### Offline addition (in `backend/tests/`, runs with the normal suite)

- **U1.** `GET /api/v1/runs`: newest first, `active_run_id`, and the
  `limit` parameter. This endpoint has no offline test today.

## Results and footprint

- Each session writes `backend/e2e/results/<YYYY-MM-DD_HHMMSS>/`,
  ignored by git, holding `results.md` and the screenshots.
- `results.md` contains:
  - **Header:** date and time, git branch and commit, database host,
    mode (stored articles or with collection), the primary classifier,
    and the topic model version.
  - **A row per check:** pass, fail or skipped, duration, and notes such
    as run IDs and article IDs.
  - **Database footprint:** row counts before and after for
    `pipeline_runs`, `pipeline_stage_runs`, `articles`,
    `classification_results` (with the number re-written) and
    `topic_results`; the run IDs created; the IDs of new articles.
  - **Failures:** the error and the screenshot for each.
- The results are produced by pytest hooks in `e2e/conftest.py`, with
  tests adding their notes through a fixture.
- Expected footprint of a default run: 2 entries in the run history (P
  and D3), 14 stage rows, about 10 LLM calls re-writing the
  classifications of the same 5 articles, and no topic rows unless one
  was missing.

## Failure handling

- A setup check that fails stops the session (`pytest.exit`) with its
  reason, since nothing after it can work.
- Every other check is independent: a failure is recorded with its error
  and screenshot, and the rest still run.
- Every wait has a limit: 5 minutes for a pipeline run, 60 seconds for
  the servers and the frontend build, 30 seconds for page loads.
- The servers, the temporary build and the browser are shut down when the
  session ends, whether it passed or failed.

## The report

`docs/testing/e2e-test-report.md`, committed, written from one full run
with `--collect`:

1. Purpose and scope, including what is out of scope and why.
2. Environment: versions, database host, topic model, classifier.
3. How to run the suite.
4. Every test: what it checks, expected result, actual result.
5. Problems found: severity, steps to reproduce, evidence.
6. The database footprint of the run.
7. Recommendations, with the separate test database first.

Two or three key screenshots are copied into `docs/testing/img/`.

**Problems the tests find are reported, not quietly fixed.** Each fix is
its own change for approval, with an offline regression test. Problems in
the test suite itself are fixed directly.

## Other changes

- `requirements-dev.txt`: add `pytest-playwright`.
- `.gitignore`: add `backend/e2e/results/`.
- `README.md`, "Running it": the e2e command and its prerequisites.
- `docs/pipeline-coordinator.md`, "Testing plan": describe the e2e suite
  and correct the outdated test count.
- `tests-to-add-later/README.txt`: say that its folders were never
  committed, so its groups need writing from scratch.

## Risks

- **LLM output varies between runs.** Tests check that classification
  rows exist and were written during the run, never their values.
- **Loading the topic model is slow** (about 30–40 seconds per run), so a
  default session takes about 3–5 minutes.
- **The shared database.** Mitigated by stored-article mode, the
  never-NewsAPI rule, a test server that cannot start a live collection,
  and the footprint section. Fully solved only by the test database.
- **Chromium download.** About 150 MB, once per machine; corporate or
  campus proxies may need configuring.
