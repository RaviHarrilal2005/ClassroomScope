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
Topic count is fixed in the saved model. Future training must be a separate, deliberate
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
cd backend
../.venv/bin/python -m agents.topic.train_auto --version discovery-v3
```

Outputs are saved in the new `models/<version>/` directory: `model.pkl`, `topics.csv`,
`assignments.csv`, `review.md`, `label-review.json`, `articles.json`, and `training.json`. Existing candidate directories cannot be
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

## Configurable discovery

Omit `--topic-count` for automatic HDBSCAN discovery. Use `--topic-count 5`
for fixed-count KMeans clustering of the article embeddings. This is a separate
training choice, not a dashboard filter or an inference parameter. KMeans assigns
every article, including weak fits; it does not provide an Unassigned category.
`--min-topic-size` applies only to HDBSCAN. Requested clusters may collapse if
input embeddings are identical; check the actual topic count in the manifest.

Replay the saved corpus to compare settings without querying Supabase:

```bash
cd backend
../.venv/bin/python -m agents.topic.train_auto --version discovery-fixed-5 \
  --snapshot agents/topic/models/auto-v2-no-forum/articles.json --topic-count 5
```

Inspect `topics.csv`, `assignments.csv`, and `review.md` before registration.
The review includes three samples per cluster and samples of unassigned articles.
Do not interpret automatic keywords as reviewed labels. Snapshots contain full
article text; keep them local unless sharing the corpus is authorized.

## Article length

The active model retains its original encoder limit of 384 tokens, including
special tokens, so long articles are represented primarily by their openings.
The experimental full-article candidate was not activated and has been removed.
Changing length handling requires a separately trained and reviewed model.

An inactive input-preparation experiment is available in
`article_representation.py`: title plus opening context and representative
source passages, bounded by the active encoder's token limit. It does not
rewrite database text or modify the saved model. `evaluate_representation.py`
compares prepared input with the current opening policy using the same model
and fallback. After a user label correction, the 20 reviewed examples match
5 labels for opening text and 7 for prepared text,
but the subsequent 20-article check, after user label corrections, matched
8 labels for opening text and 10 for prepared text, with four improvements and
two regressions. The preparation policy remains
inactive in normal runs. See `review/article-representation-v1/report.md`.

## Current Unassigned policy - November 1, 2026

The user selected review-only suggestions. A raw Unassigned result now stays
Unassigned with a null stable topic ID, even if the similarity second check
finds a qualifying match. Suggested fields and diagnostics remain available;
`topic-cosine-0.85-gap-0.03-review-only-v3` identifies the new suggestion policy.
Final assignment methods remain `bertopic-single-document-v1`. Suggestions do
not contribute to assigned counts. Existing database rows are preserved and no
historical assignments are backfilled. There is no review queue UI yet.

The descriptions below of automatic fallback promotion are historical behavior,
superseded by this policy for new inference.

## Historical Unassigned second check

After the saved model returns Unassigned, the agent compares that article's
embedding with the registered model's topic embeddings. It records a suggested
topic only when cosine similarity is at least 0.85 and the lead over the next
topic is at least 0.03. This experimental rule is identified as
`topic-cosine-0.85-gap-0.03-v1`. Similarity is not a confidence probability.
Assigned articles are not checked. A qualifying second-check match replaces
Unassigned in the final topic fields and counts toward assigned totals. The raw
model result is retained in `original_topic_id`, and `assignment_method` records
`bertopic` or the versioned fallback policy. A weak or ambiguous match stays
Unassigned without a suggestion.
Best similarity and gap are saved even when no suggestion qualifies.

Apply both `supabase/migrations/20261012000100_topic_second_check.sql` and
`supabase/migrations/20261012000200_topic_fallback_assignment.sql` before running
the updated agent against Supabase. Existing rows are preserved by the insert-only
save policy, so this does not backfill previously stored Unassigned articles.
The second check uses the same embedding strategy as the registered model;
the active model still uses its original opening-text strategy.

The fallback migrations were applied to Supabase on October 12, 2026. A separate
guarded update assigned the 22 previously tested Unassigned articles. Normal
runs still preserve historical results. The previous records and update audit
remain under `review/unassigned/deployment/`.

Human review matched 10 of the 22 fallback assignments (45.5%). The user chose
to retain automatic fallback assignment. This sample agreement is not an
independent estimate of overall model accuracy.

## Inactive reviewed-label candidate

`reviewed_candidate.py` builds a separate supervised classifier from the human
review worksheets and agreed topic definitions. It does not change the registry,
catalog, active model, or Supabase. T001–T005 and Unassigned are candidate outputs.
The first comparison uses the active encoder's original opening-text policy;
the optional lexical comparison uses whole article bodies.

From the project root, using a new output directory:

```bash
.venv/bin/python -m backend.agents.topic.reviewed_candidate --output review/topic-candidate-v1
.venv/bin/python -m backend.agents.topic.reviewed_candidate --output review/topic-candidate-v1 --full-text
```

Completed outputs refuse overwriting. Training examples and vectors are saved
locally for reproducibility. Development scoring holds out each normalized-text
group; it is not a final independent accuracy evaluation. The trained candidate
is inactive, and its current results do not justify replacing the active model.
See `review/topic-candidate-v1/report.md` for the comparison and limitations.

## Full-body candidate evaluation (October 19, 2026)

`full_context_candidate.py` evaluated token-weighted pooling of all body sections
on the 62 corrected review labels. Grouped development agreement fell from
33/62 for the opening candidate to 29/62; a separate rejection gate achieved
28/62. Both full-body candidates assigned all five human-Unassigned cases.
They remain inactive. Full token coverage is not evidence of correct scope or
content-sufficiency judgments. See `review/topic-candidate-v4-full-context/report.md`.
No active representation, saved production model, or database results changed.

## Explicit scope/content prototype (October 19, 2026)

`scope_assessment.py` prepares full-article, label-free assessment requests using
the confirmed scope and substantive-content boundaries. Structured judgments
require exact source quotations; uncertain, invalid, or failed responses require
review rather than silently becoming Unassigned. The prototype is inactive.
Its 62-article development pack is prepared but has no model accuracy results:
`TRUSSED_API_KEY` and `TRUSSED_BASE_URL` are currently missing. Ten controlled
checks passed; these are framework tests, not classification evidence. See
`review/topic-scope-content-v1/report.md` for readiness and evaluation instructions.

## Proposal audit (October 25, 2026)

F.8 calls for unsupervised discovery, configurable topic count, keywords,
readable labels, and per-article assignments. Keep discovery separate from
routine inference; the five registered IDs are not the only possible discovered
themes. The proposal does not require every run to retrain or force an assignment.

New training runs additionally remove case/whitespace-normalized duplicate bodies,
record removed IDs, and create `label-review.json` with pending readable labels,
representative article IDs, and no assumed permanent topic mapping. Existing
snapshots and saved production assignments are not rewritten. Requested KMeans
counts force coverage; HDBSCAN can return Unassigned or no clusters.

For the traditional NLP comparison, from the project root:

```bash
.venv/bin/python -m backend.agents.topic.benchmark_discovery \
  --candidate backend/agents/topic/models/discovery-fixed-5 \
  --topic-count 5 --output review/discovery-lda-new
```

This trains a seeded LDA baseline on the exact candidate snapshot and compares
keyword diversity, document co-occurrence NPMI, coverage and grouping agreement.
It is not held-out classification accuracy. No database writes or activation occur.
Local snapshots are needed and remain excluded from Git. Old candidate binaries
were removed during cleanup; retained CSVs demonstrate past training outputs,
not that those old candidate models can currently be loaded.

See `docs/topic-agent-proposal-audit.md` for requirement status and remaining work.

## Batch-independent inference (October 25, 2026)

UMAP's transform of fixed article embeddings was observed to change with input
batch composition, changing a raw topic between T002 and Unassigned. Inference
now calls the saved model once per article, and the fallback also embeds each
article separately. This establishes a canonical singleton context without
retraining, changing source text, modifying thresholds, or rewriting old results.

New primary records use assignment method `bertopic-single-document-v1`.
Fallback provenance uses `topic-cosine-0.85-gap-0.03-single-document-v2`.
Historical methods remain valid descriptions of older batch-based results.
The model checksum and topic mapping remain unchanged; the inference policy is
separately versioned. Single-document inference can be slower on large batches.

Seven real articles had identical raw and final labels across forward, reverse,
smaller-batch and individual runs. This does not establish stability across
library/hardware changes or topic accuracy. Earlier evaluation numbers describe
their historical batches; use the new singleton evaluation for the current code.
See `docs/topic-inference-consistency.md`.

## Result provenance - November 1, 2026

Apply `supabase/migrations/20261101000100_topic_result_provenance.sql` before
running updated inference against Supabase. The migration is prepared locally;
it has not been applied by this session. New records carry `mapping_version`,
a SHA-256 of canonical catalog definitions, model mapping and display labels,
and `unassigned_reason` (`uncertain_fit` for outliers, null when assigned).
Historical rows retain nulls; no backfill invents missing provenance. Content
and scope reasons require explicit assessment and are not inferred from outliers.
Ten focused offline tests passed for the code change, including provenance
changes on definition edits, saved reasons and preservation of legacy rows.
