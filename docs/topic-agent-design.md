# BERTopic-primary design decision - November 1, 2026

The user selected BERTopic as the primary discovery and routine assignment method. See [topic-agent.md](topic-agent.md) for current behavior. This supersedes the hybrid-primary recommendation preserved in the history below. Language-model assignment is optional and inactive. Model/category accuracy remains provisional; selecting the simpler method does not resolve mixed clusters.

# Topic agent design record

The final hybrid architecture and current implementation are documented in [topic-agent.md](topic-agent.md). This file retains the earlier November 1 decisions and code-review history. Statements below about the active saved BERTopic assignment describe the previous baseline; the semantic-primary implementation described in that historical note was subsequently superseded by the BERTopic decision above. Earlier implementation gaps concerning discovery-cluster registration do not block semantic category assignment, which has its own versioned five-category contract.


Design decisions agreed November 1, 2026. This document separates the intended design from the current implementation; it does not certify model accuracy or project acceptance.

## Purpose and scope

Identify the primary theme of eligible news articles about generative AI in education, support recurring-theme analysis, and provide stable topic filters. Topic analysis is separate from sentiment, stance, source type and stakeholder classification.

## Reporting categories

| ID | Category | Main subject |
|---|---|---|
| T001 | Student adoption and learning effects | Student use/adoption of AI and effects on learning, thinking, skills or academic performance. Institutional adoption alone is excluded. |
| T002 | Policy and governance | Institutional rules, restrictions, oversight, privacy and permitted AI use. |
| T003 | Classroom practice | Educator use of AI in teaching, instructional materials, assignments and assessment. |
| T004 | Academic integrity and detection | Cheating, authorship, misconduct and AI-detection reliability. |
| T005 | AI literacy | Learning to understand, evaluate and responsibly use AI. |

Choose one primary category from the central subject, not passing mentions. Learning-effects studies and student-use surveys belong in T001; a teaching method belongs in T003 even if improved learning is its goal. Teaching a subject using AI is T003; teaching understanding of AI itself is T005. Rules are T002 when central; misconduct/detection is T004 when central. Broad institutional adoption without substantive fit to a category remains outside the catalog. No automatic priority ordering resolves every overlap.

Unassigned is an outcome outside the five categories. The user confirmed exactly three reasons:

| Reason code | Display name | Meaning |
|---|---|---|
| `insufficient_content` | Insufficient content | Too little substantive article text to assess. |
| `outside_groups` | Outside the five groups | The main subject does not fit any reporting category. |
| `uncertain_fit` | Uncertain fit | No supported category can be selected, including a discovered theme awaiting mapping review. |

There is no separate unmapped-theme reason. Processing failures remain Failed, not Unassigned. Do not infer content insufficiency or outside-category scope from a BERTopic outlier alone: its supported reason is `uncertain_fit`. Empty text is currently skipped before inference. The code now emits `uncertain_fit` for model outliers and null for assigned results. Migration `20261101000100_topic_result_provenance.sql` adds nullable storage fields; the user applied it and a live read verified both fields. The other two reasons require explicit content/scope checks or human review before use.

## Two separate workflows

### Discovery and model review

1. Prepare a versioned, screened corpus, retaining reviewed exclusions and duplicate decisions.
2. Run BERTopic discovery. Omitted topic count uses HDBSCAN; configured count uses KMeans. Five reporting categories do not imply five discovered clusters.
3. Export keywords, assignments, representative articles, environment details and input/model checksums.
4. Review central and less-central members for coherent themes and suitable labels.
5. Map supported themes to reporting categories. Multiple clusters may map to one category; unsupported themes remain unmapped.
6. Compare against LDA on the same corpus and record semantic review and assignment evaluation.
7. Register a reviewed model and mapping explicitly. Training never automatically activates a candidate.

### Routine article processing

Approved article IDs -> eligible cleaned text -> checksum-verified saved model -> per-article inference -> reviewed category mapping -> structured result -> insert-only storage -> dashboard.

Normal inference does not train or change topic count. The intended contract accepts article ID, title and cleaned body. Current inference uses the body and does not read the title. Empty/ineligible inputs currently produce no topic row, rather than a stored insufficiency decision.

## Model update and activation policy

Confirmed by the user on November 1, 2026:

- Routine articles use the saved, approved model; inference never retrains it.
- Retraining is a deliberate operation on a reviewed, versioned corpus.
- Newly trained models remain candidates until themes, category mappings and evaluation results are reviewed.
- Activation explicitly registers a reviewed model and mapping. Cluster numbers do not establish semantic identity across versions.
- Activation preserves historical stored results. Reprocessing is a separate, explicitly requested operation with recorded provenance.

The current insert-only storage policy does not implement replacement reprocessing. Before offering it, define how previous results are retained and how the dashboard selects the applicable version.

## Current implementation

- `backend/agents/topic/topic_model.py`: loading, eligibility, inference, fallback, saving and agent entry points.
- `backend/agents/topic/topic_catalog.json`: model checksum, provisional labels and stable-ID mapping.
- `backend/agents/topic/train_auto.py`: separate candidate training and review exports.
- `backend/agents/topic/benchmark_discovery.py`: same-snapshot LDA comparison.
- `backend/agents/topic/TOPIC_IDENTITY.md`: operating details and historical policies.
- `backend/orchestrator/topic_counts.py` and the corpus API: dashboard topic data.

Eligibility requires both relevance flags, successful processing and nonempty `clean_content`. Present duplicate hashes are removed within the supplied batch. Discovery additionally removes normalized-text duplicates. This does not establish corpus quality or preserve all historical review exclusions.

The registered model is `provisional-v2`. Inference verifies its SHA-256, model topics and embedding strategy. Every article is transformed separately to avoid observed batch-dependent behavior. Its encoder represents primarily article openings (384 tokens including special tokens); passing a full body does not mean the model understands the full article.

For raw Unassigned results, a review-only second check suggests the closest registered topic when cosine similarity >= 0.85 and the gap to the next topic >= 0.03. The final topic remains Unassigned and its stable ID remains null; suggestions do not count as assignments. The suggestion policy is `topic-cosine-0.85-gap-0.03-review-only-v3`. Similarity is not a correctness probability. This policy was selected by the user on November 1, 2026. Historical automatic fallback assignments remain unchanged; there is no automated review queue or approval interface.

## Output and storage contract

| Existing field(s) | Meaning |
|---|---|
| `article_id` | Source article identity |
| `topic_id`, `topic`, `topic_keywords` | Final model topic, registered display label and keywords |
| `stable_topic_id` | T001-T005, or null for Unassigned |
| `model_version` | Registered model version |
| `mapping_version` | SHA-256 identity of catalog definitions, mapping and registered labels |
| `unassigned_reason` | `uncertain_fit` for model outliers; null for assigned results |
| `original_topic_id` | Raw result before fallback |
| `assignment_method` | Primary or fallback policy version |
| `suggested_topic`, `suggested_stable_topic_id` | Qualifying fallback result |
| `suggested_topic_similarity`, `suggested_topic_gap`, `suggestion_method` | Fallback diagnostics and policy |

`topic_id = -1` represents Unassigned. Results are inserted into Supabase `topic_results` with conflicts on article ID ignored; historical assignments are preserved. Report actual inserted and preserved counts. Standalone processing returns success/skipped/failed; coordinator stage handling records agent failures. There is no current per-article review queue. New results include `unassigned_reason` and `mapping_version`; the provenance migration was applied and its fields verified live. Mapping version is a SHA-256 of canonical category definitions, mapping and registered labels, reflecting the actual catalog rather than proposed definitions. Legacy rows remain null.

## Alignment work before implementation sign-off

| Agreed design | Current gap / required action |
|---|---|
| Student-only T001 | Historical catalog includes curriculum-centered institutional adoption. Review mapped members and reference labels before changing active registration or claiming compliance. |
| Many discovered themes may share one category | Registration currently rejects repeated stable IDs. Change validation and verify downstream behavior before activating such a mapping. |
| Unmapped discoveries remain Unassigned | Current active registration expects every non-outlier model topic to be mapped. Implement explicit partial mapping before activation of an unmapped candidate. |
| Reasoned Unassigned outcomes | Code emits uncertain_fit for outliers; the nullable-column migration was applied and verified. Current inference does not establish scope/content judgments. |
| Versioned category mapping | Code records a catalog/mapping hash; the prepared migration was applied and verified. Historical rows remain unchanged. |
| Reviewed training corpus | Apply a versioned exclusion/copy manifest and address extraction defects before retraining. |
| Evidence for final quality | Evaluate fresh articles labeled without seeing predictions, including all five categories and outside-catalog cases. |

The review-only suggestion policy was implemented following user confirmation. No model, threshold, database row or active registration was changed. New reference-label decisions are recorded separately in the category review overlay.

## Evaluation and limitations

Saved October 29 development comparisons on the same 62 reviewed articles: active singleton agent 23/62 matches; optional local semantic classifier 35/62; example-guided candidate 37/62. The guided variant improves classroom practice but regresses learning-effects decisions. These are reused development examples under earlier labels, not independent accuracy estimates and not results for the newly narrowed student-only T001.

Retain BERTopic discovery to satisfy proposal F.8. Local supervised/LLM candidates remain supplementary experiments. LDA grouping comparisons are distinct from held-out classification accuracy. Final validation must report per-category errors, coverage, incorrect assignments, Unassigned behavior and regressions, together with a live storage/dashboard demonstration. The proposal supplies no numeric topic-accuracy acceptance threshold; agree any such threshold explicitly.

## Operating instructions

From the repository root, install the backend requirements in the project environment and configure the shared backend environment as described in the main README. Restore the Git LFS model and apply the documented topic migrations before a live run.

```sh
cd backend
../.venv/bin/python -m agents.topic.topic_model
```

The command above writes new results to Supabase. For a deliberate discovery candidate use a fresh version name:

```sh
cd backend
../.venv/bin/python -m agents.topic.train_auto --version discovery-reviewed-v3
```

Add `--topic-count 5` only when deliberately testing five clusters. Candidates are not activated automatically; KMeans forces assignment and does not offer HDBSCAN outliers. See TOPIC_IDENTITY.md for snapshot replay and LDA benchmarking.

## Proposal traceability

Source: Revised Group 2 Project Proposal.pdf, supplied November 1, 2026. F.8 traceability (page 16) requires unsupervised discovery, configurable count, keywords, readable labels and per-article assignment. Section 2.6 (page 12) describes theme grouping; F.10 requires traditional NLP comparison; F.12 requires storage; F.14 requires topic filtering; section 3.4 (page 20) requires review of meaningful generated themes. The five reporting categories are the chosen project design, not an explicit five-category proposal requirement.

## Supporting records

- `topic-agent-validation.md` (validation and activation procedure)
- `topic-agent-implementation-checklist.md` (remaining work)

- `topic-category-review-2026-11-01.md` (confirmed category decisions under the new scope)

- `topic-agent-proposal-audit.md`
- `topic-inference-consistency.md`
- `fresh-corpus-audit-2026-10-29.md`
- `topic-boundary-examples-result.md`
- `local-semantic-classifier-result.md`

Earlier reports describe their dated experiments and definitions. Use this document for the agreed design and its explicit implementation gaps.

## First category review completed - November 1, 2026

The user completed a deliberately selected example review spanning all five historical clusters. Confirmed decisions and rationale are in `topic-category-review-2026-11-01.md`. Mixed membership was observed in every reviewed cluster. The five reporting categories remain the agreed design, but remapping existing clusters alone cannot reproduce all confirmed article decisions. These examples are development evidence; do not use them as an independent final accuracy test. The saved model remains provisional pending an evaluated model/assignment change. Review-only suggestions preserve outliers but do not identify every erroneous named assignment.

## Live schema status - November 1, 2026

The user applied the provenance migration; live reads verified both fields. A controlled run inserted article 54, read back all emitted fields and confirmed repeated insert preserves the row. The user also applied the guarded migration removing unused topic_results.run_id; verification confirmed all required result fields remain and the table contains 350 results. The assigned example did not exercise live Unassigned suggestions. See topic-agent-live-check-2026-11-01.md. No browser/dashboard demonstration has been completed.
