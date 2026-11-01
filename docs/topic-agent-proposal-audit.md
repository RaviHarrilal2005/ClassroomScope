# Topic agent audit against the revised proposal

Audited October 25, 2026. Source: Revised Group 2 Project Proposal, F.8 (page 6 and traceability page 16), Analysis Agents section 2.6 (page 12), Software section 3.2 (page 18), Testing section 3.4 (page 20), and system requirements F.10/F.12/F.14. This is an implementation audit, not project acceptance or proof of topic accuracy.

## Requirement status

| Requirement | Evidence | Status and remaining work |
|---|---|---|
| Unsupervised topic discovery | `train_auto.py` fits BERTopic without human labels; retained automatic run found four themes on 322 articles | Implemented separately from routine inference. Old candidate binaries were deleted; retained outputs are historical evidence. Regenerate a reviewed candidate before activation. |
| Configurable topic count | Automatic HDBSCAN when omitted; `--topic-count` requests KMeans clusters | Implemented as training configuration, not a dashboard control. Fixed-count mode forces assignments; requested cluster counts may collapse on identical embeddings. |
| Keyword extraction | `topics.csv`, `assignments.csv`, BERTopic c-TF-IDF output | Implemented. Generic keywords and source artifacts still affect interpretability. |
| Readable labels | Active catalog has reviewed, provisional five-topic names | Partial for new discoveries. Added structured `label-review.json` export; labels and permanent IDs require semantic review before activation. No automatic promotion. |
| Per-article assignment | Active saved-model transform, Unassigned handling, provenance, insert-only save policy | Implemented; substantial semantic errors remain in reviewed samples. Discovery clusters must not inherit T001–T005 by numeric position. |
| F.10 traditional NLP comparison | Added `benchmark_discovery.py`, ran seeded LDA comparisons on identical snapshots | Topic-side comparison now available. Whole-system benchmarking of other agents is outside this audit. |
| F.12 stored results | Active insert-only Supabase save and integration tests | Covered by controlled tests and previous live pipeline evidence; this audit did not perform a new live insertion. |
| F.14 topic filters and dashboard counts | Current corpus/data-access layer reads `topic_results`, filters by stable topic, and counts real rows | Implemented in the newly merged code. Fixed the all-Unassigned facet losing its count. No new live browser/database session was run. |
| Meaningful themes, proposal section 3.4 | Inspected keywords and first-three article excerpts for each automatic cluster | Partial: themes exist, but some samples mix meanings and source artifacts. Representative excerpts alone do not establish cluster-wide coherence. |

The proposal specifies discovery and meaningful themes; it does not specify a five-label taxonomy, an accuracy target, mandatory retraining on every run, or an LLM API dependency for topic modeling. A supervised classifier may be a supplementary comparison but is not a replacement for the stated discovery requirement.

## Changes made

1. Added same-corpus LDA benchmarking with snapshot verification, assignment-ID/count consistency checks, recorded input/output hashes, coverage, keyword diversity, document-level NPMI, and adjusted mutual information. Refuses to overwrite output. Does not activate models or write to Supabase.
2. Future training removes case/whitespace-normalized duplicate article bodies before fitting and records the removed IDs. This addresses duplicates with different stored hashes; it does not detect paraphrases or syndicated near duplicates.
3. Future training exports pending label records with cluster ID, count, keywords, representative article IDs, and empty readable-label/stable-ID fields. Pending drafts cannot be mistaken for registered production topics.
4. Dashboard topic facets preserve the true Unassigned count even when no articles have a named topic.

## Real baseline comparison on the saved 322-article corpus

| Metric | Automatic BERTopic | LDA (4) | Fixed BERTopic/KMeans (5) | LDA (5) |
|---|---:|---:|---:|---:|
| Discovered/requested topics | 4 | 4 | 5 | 5 |
| Assigned articles | 238 | 322 | 322 | 322 |
| Unassigned articles | 84 | 0 | 0 | 0 |
| Keyword diversity | 0.775 | 0.825 | 0.840 | 0.840 |
| Mean document NPMI | 0.108 | 0.094 | 0.155 | 0.103 |

All keyword measures use up to ten words per topic. NPMI uses full-body document co-occurrence and is descriptive corpus coherence, not human agreement. LDA and KMeans force an assignment, so 100% coverage is not evidence of better topics. The automatic BERTopic/LDA grouping agreement is low (adjusted mutual information 0.053); the five-topic comparison is also low (0.102). Neither score establishes which grouping is correct. BERTopic's saved representation emphasizes article openings while the LDA baseline reads full bodies, so this is not an isolated test of clustering algorithms.

Local full results: `review/discovery-auto-lda-comparison-2026-10-25/` and `review/discovery-lda-comparison-2026-10-25/`. Original snapshots and candidate outputs were not modified.

## Data quality and cluster review

The snapshot contains two normalized-text duplicates that its original content-hash deduplication missed. Future training removes those; the completed comparison deliberately retains the original corpus so it compares the exact same articles.

The fixed five-cluster run includes a four-article finance/Federal Reserve cluster, unrelated to AI education. That is a corpus-screening problem, not a sixth education theme. Similar content appears repeatedly in its sample excerpts; normalized duplicate removal does not establish removal of all related contamination. Do not automatically delete database records based on this audit.

Tentative interpretations of the automatic clusters from keywords and limited excerpts:

| Local cluster | Count | Assistant interpretation | Concern |
|---|---:|---|---|
| 0 | 102 | K–12 AI policies and adoption | Generic terms, repeated coverage of the same policy event; may blend policy with learning effects. |
| 1 | 53 | Institutional AI adoption and educator preparation | Faculty training, career readiness, and institutional adoption overlap. |
| 2 | 50 | AI use, literacy, and learning effects | Includes a short podcast summary and concrete classroom accounts; content sufficiency and topic separation need review. |
| 3 | 33 | Academic integrity and assessment | Some samples are clear cheating stories, but an institutional ChatGPT rollout also appears; not a uniformly coherent integrity cluster. |

These are assistant interpretations, not approved labels or stable catalog mappings. Article statements were assessed for thematic fit, not independently fact-checked.

## What remains before October 31

1. Prepare a screened discovery corpus: flag unrelated finance/test material, extraction artifacts, repeated coverage, and any source-policy violations with the collection owner. Keep exclusions and reasons reproducible; do not change source records silently.
2. Train a new candidate on that corpus using the updated deduplication, retain its binary, and record the exact settings and snapshot. Compare automatic discovery with a requested count without treating five as a required taxonomy.
3. Review representative and borderline articles across every cluster, assign readable labels, and document overlaps and Unassigned reasons. Assistant review can triage, but project acceptance should involve a teammate or sponsor.
4. Compare the new candidate with LDA and assess new article assignments. Corpus coherence is supplementary evidence, not a replacement for semantic review.
5. Register only a reviewed candidate with a checksum and correct permanent IDs; then verify new-result insertion, dashboard topic filtering/counts, and preservation of historical results. Current inference and Supabase results remain unchanged by this audit.

## Verification

221 automated checks and five subtests passed, including new coverage for normalized-text training deduplication, pending label exports, coherence edge cases, and all-Unassigned dashboard counts. Two real LDA baseline fits completed. No external model requests, live collection, database updates, or production-model activation were performed.
