# Pipeline Coordinator (SS-4)

**Status: groundwork in place.** The sequencing and failure handling are
built and tested (20 tests). Every agent is still a stub, and run status
is kept in memory until the `pipeline_runs` / `pipeline_stage_runs`
tables exist.

## What it does

The coordinator runs the agents in a fixed order and records what
happened at each step:

**Collection → Security → Analysis (sentiment, topic, classification, stance, all at once) → Aggregation**

It moves *control*, not data. Agents read articles from the database and
write their own results back; the coordinator only tells each agent when
to start, passes along article IDs, and records whether each stage worked.

![Pipeline sequence](images/pipeline-sequence.png)

## Failure rules

| Stage | Attempts | If it still fails |
|---|---|---|
| Collection | 3 (waits 2s, then 4s) | Run **fails** — nothing to analyze. Later stages marked `skipped`. |
| Security | 2 | Run **fails** and analysis is skipped, so unscreened content is never analyzed. |
| Sentiment | 2, then fallback agent | Stage marked `failed`; the other analysis stages keep going. |
| Topic / Classification / Stance | 2 | Stage marked `failed`; the other analysis stages keep going. |
| Aggregation | 2 | Run is `completed_with_errors`; analysis results are kept. |

Each run ends in one of three states:

- `completed` — every stage that needed to run succeeded
- `completed_with_errors` — finished, but at least one stage failed (the rest of the results are kept)
- `failed` — stopped early, or no analysis stage succeeded

A run is never left stuck at `running`: if the coordinator itself hits an
error, the run is recorded as `failed` with the error in its notes.

Retry counts and wait times are starting values in `orchestrator/retry.py`.

## Code layout

```
backend/
  app.py                    Flask app; registers the /api/v1/runs endpoints
  run_pipeline.py           terminal demo — runs the pipeline once and prints a table
  orchestrator/
    stages.py               stage names, order, and status values
    models.py               run/stage records (match the proposed tables column for column)
    agents.py               the agent contract + stub agents
    registry.py             which agent runs each stage — edit this to plug in real agents
    retry.py                attempts and backoff per stage
    coordinator.py          sequencing and failure handling
    runner.py               runs the pipeline on a background thread
    routes.py               API endpoints
    store.py                where run status is saved (in-memory for now)
    supabase_store.py       Supabase version of the store (draft, see below)
  tests/                    20 tests (more get added as features land)
docs/
  pipeline_tables.sql       draft SQL for the two run-tracking tables
```

## Running it

From the `backend` folder:

```
pip install -r requirements-dev.txt

python run_pipeline.py                      # normal run
python run_pipeline.py --fail topic         # one analysis agent fails
python run_pipeline.py --fail sentiment     # sentiment fails, fallback takes over
python run_pipeline.py --fail security      # screening fails, analysis skipped
python run_pipeline.py --flaky collection   # fails once, succeeds on retry

python -m pytest tests                      # run the tests
```

Through the API (with `python app.py` running):

```
curl -X POST http://localhost:5000/api/v1/runs      # start a run -> 202 with the run ID
curl http://localhost:5000/api/v1/runs/1            # progress of run 1, stage by stage
curl http://localhost:5000/api/v1/runs              # recent runs, newest first
```

Starting a run while another is active returns `409` with the active run's ID.

## Testing plan

The 20 current tests cover this week's work: stage order, the four
analysis agents running at the same time, each failure rule, and the
API. Tests get added alongside the features they cover:

| When we... | Add tests for |
|---|---|
| switch to the Supabase tables | the Supabase store, and a check that the SQL and code stay in sync |
| plug in the real agents | malformed output, duplicate articles, quarantined articles, misbehaving agents |
| have the dashboard poll run status | the run-list and run-status endpoints |
| settle the retry settings | retry counts and backoff timing |
| add scheduled runs or single-stage re-runs | run lifecycle rules |

## For agent owners: plugging in your agent

1. Subclass `Agent` from `orchestrator/agents.py` and implement `run(ctx)`.
2. `ctx` holds `run_id`, `article_ids` (collected), `approved_ids`
   (passed security), and `completed_analysis` (for aggregation). It
   never holds article text — read what you need from the database.
3. Write your results to your own table, then return a small summary dict.
4. If something goes wrong, **raise an exception**. Don't retry inside
   your agent and don't swallow errors — the coordinator handles retries,
   fallbacks, and recording the failure.
5. Replace your stage's stub in `build_default_registry()` in `registry.py`.

What each stage must return (the coordinator checks this and treats
anything else as a failure):

| Stage | Return value |
|---|---|
| Collection | `{"article_ids": [...]}` — IDs of the articles stored this run |
| Security | `{"approved_ids": [...], "quarantined_ids": [...]}` — approved IDs must come from the collected ones |
| Sentiment / Topic / Classification / Stance | any dict, e.g. `{"processed": 42}` |
| Aggregation | any dict |

Example:

```python
from orchestrator.agents import Agent

class SentimentAgent(Agent):
    name = "sentiment"

    def run(self, ctx):
        # read articles ctx.approved_ids from the database,
        # classify them, write rows to sentiment_results
        return {"processed": len(ctx.approved_ids)}
```

```python
# registry.py
registry.register(SENTIMENT, SentimentAgent(), fallback=agents.stub_fallback(SENTIMENT))
```

## Switching to Supabase (once the tables exist)

1. Create the tables from `docs/pipeline_tables.sql`.
2. Uncomment `supabase>=2.0` in `requirements.txt` and reinstall.
3. Set `SUPABASE_URL` and `SUPABASE_KEY` as environment variables.
   **Never commit the key to the repo.**
4. In `app.py`, replace `InMemoryRunStore()` with `SupabaseRunStore.from_env()`.

`supabase_store.py` hasn't been run against a real database yet, so
check one real run after switching.
If row-level security is enabled on the new tables, the backend needs a
policy that lets it write run status.

Tests for the Supabase store get added as part of the switch, including
one that fails if the SQL file and the code drift apart.

## Known limitations and next steps

- **No per-stage timeout.** An agent that hangs holds up its run.
- **Runs live inside the Flask process.** If the server stops mid-run,
  that run stays at `running`. A startup check that marks stale runs as
  `failed` would fix this.
- **No single-stage re-run yet.** Re-running just one stage needs to know
  which articles belonged to the run — see open question 3.
- **No auth on `POST /api/v1/runs`.** Should be admin-only once login (SS-5) exists.
- **Nothing schedules runs yet.** The `scheduled` trigger type is ready,
  but no scheduler calls it.
- **The dashboard doesn't poll run status yet.** The endpoint it needs exists.

## Open questions for the team

1. **Who writes results?** This assumes each agent writes its own result
   rows. If we'd rather agents return results for the coordinator to
   write, only the agent contract changes — not the sequencing.
2. **When does screening happen?** This assumes collection stores articles
   and returns their IDs, and security then approves or quarantines them.
   If nothing should be stored before screening, collection would hand
   over unsaved articles instead — a small change to the collection and
   security contracts.
3. **Add `run_id` to the four results tables?** It would let us filter
   results by run and clean up a failed run's partial output. Commented
   out at the bottom of `pipeline_tables.sql`.
4. **Stage names.** The SQL adds `security` and `stance` to the original
   proposal and names the last stage `aggregation` rather than `aggregate`.
