# Topic agent operating guide

BERTopic selected as the primary method on November 1, 2026. The language-model implementation is archived locally and is not a pipeline option. This guide supersedes earlier hybrid-primary recommendations.

## Primary workflow

1. The coordinator supplies security-approved article IDs.
2. The agent reads eligible articles with both relevance flags true, successful processing and nonempty cleaned text; present duplicate hashes are filtered within the input batch.
3. Load the checksum-verified `provisional-v2` saved BERTopic model. Transform each article separately for consistent batch context. No retraining occurs during inference.
4. Translate internal topic IDs through the registered provisional T001-T005 mapping.
5. Raw Unassigned results remain Unassigned, even when cosine similarity supplies a suggested category. Suggestions never contribute to assigned counts.
6. Insert new results into Supabase while preserving existing article rows. Return processed, assigned/unassigned and inserted/preserved counts.

## Five reporting groups

| ID | Agreed meaning |
|---|---|
| T001 | Student adoption and learning effects; institutional adoption alone is excluded. |
| T002 | Institutional policy, governance, restrictions, privacy and permitted use. |
| T003 | Educator practices in teaching, materials, assignments and assessment. |
| T004 | Academic integrity, cheating, authorship, misconduct and detection reliability. |
| T005 | AI literacy: understanding, evaluating and responsibly using AI. |

These are intended reporting definitions. The existing model/mapping remains provisional: reviewed members mix categories, and the historical catalog includes broader T001 scope. Editing labels alone cannot enforce the new boundaries. Human-confirmed article decisions are maintained separately in `topic-category-review-2026-11-01.md`; database rows and historical metrics are not silently rewritten.

## Unassigned and provenance

The agreed reasons are insufficient_content, outside_groups and uncertain_fit. Current BERTopic outliers use uncertain_fit; the model does not establish the other two judgments. Empty/ineligible text is skipped before inference. Processing failures are separate from Unassigned.

New results record article ID, internal topic ID, stable category ID, registered label/keywords, model version, mapping/definition hash, original topic ID, assignment method and Unassigned reason. Review suggestions retain their separate fields, similarity and gap. Similarity is not a correctness probability. Legacy rows may have null provenance. There is no review-queue UI.

## Configuration and running

Use Python 3.12 and install `backend/requirements.txt`. Restore the trusted registered model with Git LFS. Set `TOPIC_METHOD=bertopic` in backend/.env; this is also the code default. No language-model API key, Qwen download or separate inference host is required.

From `backend/`, dry-run a file without database access:

```sh
python -m agents.topic.assign --text-file /absolute/path/article.txt
```

The standalone live command reads eligible records and inserts new results:

```sh
python -m agents.topic.topic_model
```

Live pipeline runs also invoke the other project agents. Do not use them as a no-write smoke test.

For evaluation, supply explicit local reference JSON containing article_id, full text and label:

```sh
python -m agents.topic.evaluate_active --references /absolute/path/references.json \
  --method bertopic --output /absolute/path/new-evaluation
```

Keep raw article/reference data and generated experiments under ignored review/.

## Separate discovery

Train a candidate deliberately using `train_auto.py`, with a new version name. Default HDBSCAN chooses the topic count and can produce outliers. The existing fixed-count option uses KMeans and forces article assignment. Five reporting groups do not require five discovered clusters.

Review keywords and central/less-central article members before assigning names and mappings. Use `benchmark_discovery.py` for a same-corpus LDA comparison. No candidate is activated automatically. Register a reviewed new version explicitly; do not reuse internal cluster numbers as semantic identities. Existing results remain preserved unless a separate reprocessing policy is implemented and authorized.

## Current evidence and limits

The saved encoder represents mainly article openings because of its token limit. Corpus audits found extraction repetition and other input defects. Whole-article averaging, subgroup splitting and increasing count to 8/12 did not demonstrate a solution to known category mixing. The more-cluster experiment used unchanged representations and a previously screened 311-article corpus; it did not test extraction repair.

The Mac language-model candidate matched 16/18 selected development labels but only 2/5 fresh user labels, compared with BERTopic's 3/5 on that small fresh set. The language model assigned categories to all three human-Unassigned examples. These samples do not establish general accuracy. Retaining BERTopic is a project-fit/readiness decision, not proof its current assignments are reliable.

The provenance migration and removal of unused run_id were verified live; 350 results remained. A historical-method run inserted article 54 and verified repeat insertion preserves it. No results were rewritten when selecting BERTopic as primary. Cloud deployment is not required, as confirmed by the user. Linux/container verification is optional and does not block local release. A local read-only API check and isolated browser replay of its captured responses passed for all five topic filters; see topic-agent-local-release.md for the exact scope.

## Archived language-model experiment

Language-model sources/tests were moved to ignored `review/archived-portable-language-model-2026-11-01/`. They remain available as historical research, but selecting semantic as a production method now fails explicitly. Active code has no imports from that archive. Existing earlier Mac experimental assets remain local as previously requested.

## Files and deployment

- `topic_model.py`: primary inference, review-only suggestions and persistence.
- `topic_catalog.json`: provisional model checksum, mapping and labels.
- `train_auto.py`, `benchmark_discovery.py`: candidate discovery and LDA comparison.
- `assign.py`, `evaluate_active.py`: database-free dry-run/evaluation.
- [Validation record](topic-agent-validation.md) and [implementation checklist](topic-agent-implementation-checklist.md).

## Local baseline verification

See [topic-agent-local-release.md](topic-agent-local-release.md) for final functional evidence and known limitations. The locally frozen baseline is functionally checked; five-category accuracy remains provisional. Collection/preprocessing changes are outside the topic-agent owner's scope.

Cloud-only packaging was removed during final cleanup because deployment is not required. Direct local setup above remains supported.
