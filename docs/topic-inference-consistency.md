# Consistent saved-model inference — October 25, 2026

## Cause and correction

The same technology newsletter (article 5231) received raw topic T002 alone and in a five-article batch, but Unassigned in the six-article assessment. With embeddings held fixed, UMAP produced different reduced coordinates and raw predictions across those batches. This isolates a batch-context dependency in the dimensionality-reduction path, rather than article changes or the fallback rule. It does not establish that UMAP is malfunctioning outside this application's need for per-article stable results.

The agent now calls the registered BERTopic model with exactly one article at a time. Fallback embeddings are also computed one article at a time to avoid batch-padding/numerical effects near a cutoff. The model is loaded once per run, not once per article. Existing eligibility checks, opening-text representation, model checksum, registered topic IDs, thresholds, insert-only persistence and historical rows are preserved.

New primary assignments record `bertopic-single-document-v1`; new fallback assignments record `topic-cosine-0.85-gap-0.03-single-document-v2`. No schema change is necessary because these existing metadata fields are text.

## Verification

Seven real articles were tested together, reversed, in a five-article subset and individually: all overlapping raw and final predictions matched. The exercise made 26 article predictions across ten caller batches and took approximately 11.9 seconds after loading the model. This includes repeated work and is not a throughput benchmark or a comparison with old batching. Singleton calls trade batch throughput for stable inference context. Stability across different hardware or library versions has not been established.

222 automated checks and five subtests passed. The new regression test uses a deliberately batch-sensitive stand-in and verifies composition/order independence. Existing pipeline tests verify singleton invocation, fallback provenance and preservation of historical rows. No database writes or external model requests were made.

## Semantic regression check

| On the same 62 human-reviewed development articles | Earlier batch inference | Canonical singleton inference |
|---|---:|---:|
| Final matches | 24/62 (38.7%) | 23/62 (37.1%) |
| Named assignments | 37 | 38 |
| Correct named assignments | 21 | 21 |
| Valid-topic articles left Unassigned | 22 | 22 |
| Human-Unassigned articles assigned a topic | 2/5 | 3/5 |

This is a consistency fix, **not an accuracy improvement**. One additional negative article is assigned a named topic; therefore semantic rejection remains a limitation. The old batch was one arbitrary context, whereas the new singleton context is fixed. Neither context proves correct labels. Do not use earlier rescue development gains as metrics for this changed inference policy without rerunning those comparisons.

Changed final labels:

- Article 5224: T005 → U; existing human label T003.
- Article 5254: U → T004; existing human label T005.
- Article 5473: U → T001; existing human label U.
- Article 5245: U → T004; existing human label T004.
- Article 5253: T002 → U; existing human label T002.

## Scope and remaining work

Only local inference and associated tests/documentation changed. No model was retrained or registered, no database results were backfilled, and nothing was pushed. The active saved model remains provisional. Next, follow the proposal audit: screen the discovery corpus, train and review a new unsupervised candidate, then assess topic quality and assignments using the now-consistent inference path. Record model identity, inference policy, package versions and source text when comparing runs.

Local evidence is under `review/model-demo-2026-10-25/` and `review/active-single-document-evaluation-2026-10-25/`; these are excluded from Git.
