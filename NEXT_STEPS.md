# What's left to do

The pipeline runs from start to finish with a real agent at every
stage. Sentiment and comment sentiment are placeholders on any computer
without their libraries, and stance on any without the Trussed keys.
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
  found 9 new articles and none were relevant; the run's note now says
  so. To test the analysis stages anyway, click **Run on 5 stored
  articles**, or use the `--backlog` command above. Both reuse articles
  we already have and fetch nothing.

## Where each stage stands

| Stage | Status | Who |
|---|---|---|
| Collection | real | Juan |
| Security | real | MDalien, vmarkkk |
| Classification | real | Juan |
| Topic | real (needs Git LFS, see above) | Esmeralda |
| Sentiment | real (needs `transformers` + `vaderSentiment`, see requirements.txt) | Deena |
| Stance | real (needs `TRUSSED_API_KEY` + `TRUSSED_BASE_URL`): for / against / neutral toward GAI in education | Ravi |
| Comment sentiment | real (needs `transformers`): readers' comments, after security screens them | Deena |
| Aggregation | real: the dashboard's sentiment figures | Ravi |

## 1. Sentiment: done, check it on a real run (Deena)

`SentimentAgent` is registered in `orchestrator/registry.py`: RoBERTa
first, VADER if the model can't load. It stays a stub where
`transformers` or `vaderSentiment` isn't installed.

To check it: `python run_pipeline.py --live --backlog --limit 5` should
show sentiment as `succeeded`, and `sentiment_results` should have new
rows for those 5 articles. The first RoBERTa run downloads the model
(over 1 GB). VADER was checked against real articles; the RoBERTa path
has not been run through the pipeline yet.

## 2. Stance and comment sentiment: done (Ravi, Deena)

Stance (`agents/stance/stance_agent.py`) asks the Luna LLM whether each
article is for, against or neutral toward generative AI in education,
the three labels of SemEval-2016 Task 6. It writes `stance_results`
with the target and method on every row, and skips articles that
already have one. Comment sentiment (`agents/sentiment/comment_sentiment_agent.py`)
is now its own pipeline stage, `comment_sentiment`, labelling the reader
comments security has passed. The dashboard shows both: a stance donut,
a "How readers react" donut, and a stance column in the article table
and the CSV.

To check it: a run shows `stance` and `comment_sentiment` as
`succeeded`. To label every article that has no stance yet:
`python -m agents.stance.stance_agent --save` from `backend/`.

Open: nobody has checked the stance labels against human ones yet
(README, "MVP features"). The kit to do it is ready; to run it, from `backend/`:

1. `python -m agents.stance.validation sample --n 50 --out stance_sample.csv`
   (reads Supabase, SELECT only; the CSV has no model stance in it).
2. Fill `human_stance` (favor, against or neutral) in a spreadsheet, without
   opening the dashboard's stance chart, the article table's stance column or
   `stance_results` first. Use the label definitions in `build_prompt`
   (`agents/stance/stance_agent.py`) so you and the model judge by the same
   criteria. Save as `stance_sample_labelled.csv` ("CSV UTF-8" in Excel; plain
   CSV works too). `score` lists any label it doesn't recognise.
3. `python -m agents.stance.validation score stance_sample_labelled.csv` prints
   accuracy, Cohen's kappa, the confusion matrix, and how many rows were skipped.

## 3. Aggregation: done, check it on a real run (Ravi)

`/api/v1/results` now serves real sentiment figures for the filtered
articles: the share (the donut), the same broken down by month, topic
and stakeholder, and the most negative stakeholder and topic
(`agents/aggregation/compute.py`). The aggregation stage computes them
on every run, so a broken table fails the stage. The dashboard draws
the monthly, stakeholder and topic breakdowns under a headline, and the
article table has a sentiment column. Still open: a snapshot per run
(README, "MVP features").

To check it: a run shows aggregation `succeeded`, and
`python -m pytest e2e -k "r1 or d1"` compares the API, the donut and
the headline with `sentiment_results`.

## 4. Dashboard (Ravi)

Built: the filter panel (date range, source type, stakeholder, topic and
keyword search), Export CSV on the article table, the dark theme that
follows the OS setting, filters and the open tab kept in the URL so a
filtered view can be shared, and the "Sentiment by month" chart. The
sentiment figures follow the filters because they are computed per
request; a snapshot table, if one is added, has to keep that. The
shortcuts are in the MVP table in README.md.

## Still open

- **Run the backend e2e suite once against the shared database.**
  `backend/e2e/test_3_dashboard.py` now expects 5 charts. From `backend/`,
  run `python -m pytest e2e`. It writes to the shared Supabase project
  (see the end-to-end section of the README). Afterwards refresh
  `docs/testing/e2e-test-report.md`, which predates the 5-chart check.
- **Hand-label about 50 stance articles and compute Cohen's kappa.**
  Nobody has checked the stance labels against human ones yet.
- **Run the RoBERTa sentiment path through a full pipeline run.** Only
  VADER has been checked on real articles (section 1).
- **The known shortcuts** are the MVP table in README.md. Each row names
  the shortcut, its ceiling, and the better version.
