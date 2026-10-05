# Saved topic model

Normal runs load `models/provisional_topic_model_v2.pkl` and call `transform`.
They do not train, change topic count, or update model files. Even a single
eligible article can be analyzed. Both relevance flags, successful processing,
and nonempty article text remain required.

`topic_catalog.json` binds the exact model checksum to `provisional-v2`, reviewed
labels, and permanent IDs T001–T005. Internal cluster numbers are meaningful
only within that model version. Unassigned articles have no stable topic ID.
These labels remain provisional pending further quality evaluation.

New assignments are inserted into Supabase. Existing assignments are preserved,
including old model versions. The run reports the actual inserted count and the
number of existing assignments preserved. Missing values are sent as JSON null.
The existing topic identity migration supplies the two metadata columns.

A missing or changed model causes an error; there is no automatic retraining.
The topic_count argument is kept for compatibility with the orchestrator but
does not change a saved model. Future training must be a separate, deliberate
operation, saved under a new filename and version. Review each new cluster before
mapping it to an existing permanent topic ID or allocating a new one. Never
reuse the old cluster numbers as evidence of topic identity.

## Separate automatic discovery training

`train_auto.py` deliberately trains a candidate using `nr_topics=None`: the
clustering chooses the number of topics. The minimum topic size defaults to 10;
it is a cluster-size setting, not a request for exactly ten topics. Automatic
discovery may find fewer or more topics than the existing model, or no clusters.

When ready to train, run from the project folder:

```bash
.venv/bin/python topic_model_agent/train_auto.py --version auto-v1
```

Outputs are saved in a new `models/auto-v1/` directory: `model.pkl`, `topics.csv`,
`assignments.csv`, and `training.json`. Existing candidate directories cannot be
overwritten. A failed attempt keeps its directory and marks its manifest failed;
use a new name for a retry. Training can download the embedding model if it is
not cached. It reads eligible articles from Supabase but performs no database writes.

The candidate is not automatically registered or activated. Its internal topic
numbers do not inherit T001–T005. Review and map candidate themes before using
them as permanent topics. Normal runs keep using the current registered model.
This command does not add continual discovery, a discovery pool, or source screening.

Run from `backend/`:

```bash
python -m agents.topic.topic_model
```

Deleting previous results allows eligible articles to receive new assignments
on the next run. Normal inference never deletes or replaces historical rows.
Only load trusted locally produced model pickle files.
