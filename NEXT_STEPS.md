# What's left to do

The pipeline runs from start to finish, but three of its seven stages
are still placeholders, and the dashboard's sentiment chart still shows
made-up numbers.
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

If you're only working on the dashboard's run console, use
`run_dev_server.py`. Runs finish in seconds and nothing touches the
shared database. It reads no database, so the dashboard shows no
articles; use `python app.py` to see real articles and topics. Its GET
endpoints only read, but don't click "Start a run" there.

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
| Sentiment | real (needs `transformers` + `vaderSentiment`, see requirements.txt) | Deena |
| Stance | stub: no code yet | TBD |
| Aggregation | stub: planned, starts after sentiment | Ravi |

## 1. Sentiment: done, check it on a real run (Deena)

`SentimentAgent` is registered in `orchestrator/registry.py`: RoBERTa
first, VADER if the model can't load. It stays a stub where
`transformers` or `vaderSentiment` isn't installed.

To check it: `python run_pipeline.py --live --backlog --limit 5` should
show sentiment as `succeeded`, and `sentiment_results` should have new
rows for those 5 articles. The first RoBERTa run downloads the model
(over 1 GB). VADER was checked against real articles; the RoBERTa path
has not been run through the pipeline yet.

## 2. Stance (TBD)

There's no stance code yet, and nothing on the dashboard uses stance
results. Whoever picks it up can follow the same steps as sentiment.
Results go in the `stance_results` table.

## 3. Aggregation (Ravi, after sentiment)

Aggregation turns the analysis tables into the numbers the dashboard
shows. The topic chart is already real: `/api/v1/results` counts
`topic_results` directly. Sentiment and the article list are still
sample data, which is why they have a yellow "Placeholder figures"
note. The plan is
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
- The filter panel and keyword search exist as MVPs (README, "MVP
  features — come back to these"). When the aggregation agent lands, its
  snapshot can't be filtered as planned, so `/results` has to keep
  filtering per request or the snapshot has to change shape.
