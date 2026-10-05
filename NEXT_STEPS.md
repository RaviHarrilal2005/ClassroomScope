# What's left to do

The pipeline runs from start to finish, but three of its seven stages
are still placeholders, and the dashboard still shows made-up numbers.
This page lists what has to change and how to tell when each part is
done.

## Before you pull: install Git LFS

The topic model (`backend/agents/topic/models/provisional_topic_model_v2.pkl`,
441 MB) is stored with [Git LFS](https://git-lfs.com). Install it before
you pull, or run `git lfs pull` afterwards. Without it you get a tiny
placeholder file instead of the model, topic quietly stays a stub, and
the backend log says `is a Git LFS pointer, not the model`.

To check it worked: start `python app.py` from `backend/` and look for
`saved topic model found, using the topic agent` in the output.

## First, how a run works

The dashboard (the page at http://localhost:5173) doesn't run any
agents. It's a remote control. When you click **Start a run**, it asks
the Python backend (http://localhost:5000) to run the pipeline, then
checks on it every two seconds. The agents always run in the backend,
because they need Python, the ML models, and the keys in `backend/.env`.

How you start the backend decides which agents you get:

| Command (run from `backend/`) | Works with the dashboard? | Agents | Writes to our shared Supabase? |
|---|---|---|---|
| `python app.py` | yes | the real ones, where they exist (needs `backend/.env`) | yes |
| `python run_dev_server.py` | yes | all stubs | no |
| `python run_pipeline.py --live --backlog --limit 5` | no, it prints to the terminal | the real ones, on 5 articles we already have | yes |

If you're only working on the dashboard, use `run_dev_server.py`. Runs
finish in seconds and nothing touches the shared database.

Two words you'll see on the dashboard:

- A **stub** is a placeholder agent. It reports "succeeded" without
  doing anything, so the pipeline can run before every agent exists.
- **Skipped** means an earlier stage left nothing to do. A dashboard
  run always starts by fetching new news. If none of it is about AI in
  education, there's nothing to analyse, so every stage after
  collection is skipped. That's what happened on run #12 (Oct 4): it
  found 9 new articles and none were relevant. To test the analysis
  stages anyway, use the `--backlog` command above, which reuses
  articles we already have.

## Where each stage stands

| Stage | Status | Who |
|---|---|---|
| Collection | real | Juan |
| Security | real | MDalien, vmarkkk |
| Classification | real | Juan |
| Topic | real (needs Git LFS, see above) | Esmeralda |
| Sentiment | stub: the script works, but the pipeline can't call it yet | Deena |
| Stance | stub: no code yet | TBD |
| Aggregation | stub: planned, starts after sentiment | Ravi |

## 1. Sentiment: turn the script into an agent (Deena)

`backend/agents/sentiment/sentiment_agent.py` already works. Its 254
results are in the `sentiment_results` table. But it's built to be run
by hand: as soon as the file is opened it loads the models, reads
`articles_rows.csv` (an export someone downloaded from Supabase),
labels every article in it, and writes CSV files for someone to upload.
The pipeline needs to call it on the articles from one run instead.

1. Move the work into functions, so nothing runs when the file is
   imported. Load the models inside a function, the first time they're
   needed.
2. Read the articles from Supabase instead of the CSV. Use
   `get_client()` from `agents/supabase_client.py`, and only fetch the
   IDs the pipeline gives you (`ctx.approved_ids`).
3. Write each result straight into `sentiment_results` (`article_id`,
   `sentiment`, `confidence`, `method`) instead of into a CSV.
4. Don't hide failures. If the step can't run at all (no model, no
   database), raise an error instead of printing it. The pipeline
   retries failed stages and records the error on the dashboard.
5. Add `transformers` and `vaderSentiment` to `backend/requirements.txt`.
6. Add a `SentimentAgent` to `agents/adapters.py` and register it in
   `orchestrator/registry.py`. `TopicAgent` in `adapters.py` is a good
   one to copy. This step can also happen when your branch gets
   merged, the way the other agents were connected.

The full checklist for plugging in an agent is in
[docs/pipeline-coordinator.md](docs/pipeline-coordinator.md#for-agent-owners-plugging-in-your-agent).

Done when: `python run_pipeline.py --live --backlog --limit 5` shows
sentiment as `succeeded`, and `sentiment_results` has new rows for
those 5 articles.

## 2. Stance (TBD)

There's no stance code yet, and nothing on the dashboard uses stance
results. Whoever picks it up can follow the same steps as sentiment.
Results go in the `stance_results` table.

## 3. Aggregation (Ravi, after sentiment)

Aggregation turns the analysis tables into the numbers the dashboard
shows. Until it exists, `/api/v1/results` returns sample data, which is
why the charts have a yellow "Placeholder figures" note. The plan is
already written in
[docs/superpowers/plans/2026-09-29-aggregation-agent.md](docs/superpowers/plans/2026-09-29-aggregation-agent.md).
Work starts once sentiment is connected, so there are real sentiment
results to count.

## 4. Dashboard fixes (Ravi)

Smaller things we found while testing:

- The "stub" tag next to each stage comes from a fixed list in
  `frontend/src/components/AdminConsole.jsx`. Topic is off the list now
  that its model is in the repo, but on a computer without the model,
  topic is a stub the dashboard won't tag. The backend should report
  which agent actually ran each stage, and the dashboard should show
  that.
- When collection finds new articles but none are relevant, the run
  says "No new articles were collected." It should say something like
  "9 new articles, none relevant."
- The dashboard can't start a backlog run, so testing the analysis
  stages needs the terminal. A "run on stored articles" button would
  fix that.
- FilterPanel is the next feature. It needs a design decision first,
  because the aggregation plan saves its results in a way that can't be
  filtered yet.
