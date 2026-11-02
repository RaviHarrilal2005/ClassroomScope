# Topic agent validation and release procedure

Prepared November 1, 2026. Companion to `topic-agent-design.md` and `topic-category-review-2026-11-01.md`. This is a procedure, not a completed validation report. The active model remains provisional.

## 1. Freeze the version being evaluated

Record model file SHA-256, model registration, category definitions and mapping version, inference and suggestion policies, preprocessing policy, dependency versions and corpus checksum. Include the student-only T001 definition. Never tune the frozen candidate using final evaluation outcomes and continue calling those outcomes untouched validation.

The current baseline uses provisional-v2 with singleton inference and review-only cosine suggestions. Code now emits a mapping/definition/label hash and structured outlier reason. Apply the prepared provenance migration before live inference; historical rows remain null. Preserve exact catalog snapshots for replay.

## 2. Review discovered themes

Inspect keywords, representative members and less-central members from every discovered cluster. Identify source artifacts, duplicate/event concentration and mixed subjects. Label clusters meaningfully; map supported themes to the five reporting categories only after review. Unsupported mappings require review, with Uncertain fit for any resulting Unassigned article. Do not assign stable IDs from cluster numbers alone.

The November 1 article review found mixed historical membership in every examined category. Those selected examples are development evidence, not a representative error-rate sample. Mapping edits alone cannot reproduce all confirmed decisions.

## 3. Assemble independent article evaluation

Choose previously unreviewed articles, excluding detected copies of development stories. Record selection rules, time range, source distribution and exclusions. Check related-event overlap. Have a reviewer read the available text and assign one category or Unassigned, without seeing predictions. Include sufficient coverage of each category and outside-category/insufficient-content cases. Record ambiguous decisions and adjudicate them before inspecting predictions where possible.

Record article identity, text checksum, reference label, Unassigned reason where applicable, reviewer and review date. Reused November 1 decisions must remain development examples. Do not claim a class-balanced sample estimates natural production prevalence without an appropriate sampling design.

## 4. Run the frozen comparison

Use identical article text and reference labels for the baseline and candidate. Save individual predictions, final category, raw topic, suggestions, version provenance, failures and runtime. Separate failures from Unassigned. Do not treat cosine similarity as a correctness probability.

Report total exact matches, per-category precision/recall with counts, confusion matrix, assignment coverage, incorrect named assignments, correct/incorrect Unassigned decisions, valid-category articles left Unassigned and processing failures. State denominators, sample sizes and selection limitations. Report baseline-correct decisions lost as well as errors corrected.

The current review-only suggestion change needs a newly measured baseline. Earlier automatic-fallback scores do not measure the new policy or the revised T001 definition.

## 5. Compare with traditional NLP

Use the same reviewed training snapshot for BERTopic and seeded LDA. Record preprocessing differences, topic-count settings, seeds and checksums. Report keyword diversity, document-level co-occurrence NPMI, coverage and grouping agreement where supported by `benchmark_discovery.py`. Supplement metrics with semantic review. Grouping agreement is not category accuracy, and a higher coherence score alone does not establish suitable article assignments.

## 6. Verify software and integration

Run the existing focused inference, discovery, benchmark, coordinator/persistence and topic-count tests. Verify model checksum failures cannot trigger retraining. Verify weak and strong suggestions both leave final outliers Unassigned, with null stable IDs and unchanged assignment counts. Preserve prior article rows on insert conflict.

Then perform a controlled live demonstration with approved article IDs: record before/after database state, inserted/preserved counts, saved provenance and dashboard topic filters/counts. Verify successful stages remain visible if another stage fails. Do not describe offline mocks as a live demonstration. A review queue UI is not currently implemented.

## 7. Decide and record activation

The proposal supplies no numeric topic-accuracy acceptance threshold. Agree any quantitative threshold before using it as an acceptance gate. Record the actual results, regressions, unresolved ambiguity, operational constraints and activation decision. A passing software suite does not establish semantic quality.

Keep the existing version provisional if evidence is inadequate. Activation must explicitly register a reviewed model/mapping and preserve historical results. Reprocessing requires an explicit operation with a defined history-retention policy; current insert-only storage does not perform replacement reprocessing.

## Evidence currently available

- Human-confirmed development decisions: `topic-category-review-2026-11-01.md`.
- Earlier experimental comparisons and caveats: `local-semantic-classifier-result.md` and `topic-boundary-examples-result.md`.
- Corpus defects requiring attention before training: `fresh-corpus-audit-2026-10-29.md`.
- The review-only code change passed 10 focused tests on November 1. It did not perform a live insertion, retraining, candidate activation or new accuracy evaluation.

## November 1 development comparison

A new comparison on the 18 user-confirmed design-review articles matched 5/18 for the current review-only BERTopic baseline and 16/18 for the optional local candidate under the student-only T001 definition. The candidate assigned all 18, including the one human-Unassigned article. It corrected 12 baseline errors and lost one correct decision. This selected, reused development set does not establish production accuracy or justify activation. Fresh independent evaluation and explicit uncertainty/reason-contract integration remain required. Full experiment records stay local at `review/design-comparison-2026-11-01/`; no database results or active model registration changed.

## November 1 exploratory 20-article run

At the user's request, further blind labeling was skipped. Both methods ran on the 20 selected article bodies without database writes. The local candidate assigned 17, returned one Unassigned and routed two over-limit inputs to review. The current review-only BERTopic baseline assigned 10 and left 10 Unassigned. Only one final label agreed between methods. Agreement is not correctness. Only V001 has a pre-prediction user reference label; this run cannot establish independent accuracy, and predictions must not guide subsequent claims of blind reference review. Candidate article hashes and accepted evidence offsets were verified. Full predictions and frozen configuration remain local under `review/blind-validation-2026-11-01/`. The candidate remains inactive.

## Portable hybrid implementation checks - November 1, 2026

Primary assignment now has an in-process Transformers/PyTorch CPU/CUDA implementation and an optional HTTP implementation, both using the shared semantic category/reason/evidence contract. Discovery remains a separate BERTopic tool. Original model revision and prompt/definition identifiers are recorded. No separate model host is required for in-process inference.

A clean export of Git-eligible files, excluding all ignored experimental modules, credentials and model binaries, passed 212 tests and 5 subtests. This includes 17 semantic contract/runtime/persistence tests. Compose YAML and module syntax were checked. The earlier broader workspace run passed 255 tests and 5 subtests before two additional CPU-path tests were added; that workspace run included ignored experiments and is not the release test count.

CPU tensor/generation-call tests use controlled model outputs; they are not a full pretrained-Qwen inference test. The original weights have not been downloaded or executed here. Docker is unavailable, and this Mac has 16 GB RAM versus approximately 16 GB for CPU float32 weights alone. Consequently a real model smoke run, Linux image build/run, measured resource envelope and independent semantic accuracy remain acceptance work. No cloud resource was launched, database result changed or Git commit pushed during this implementation.

## Quick blind-reference check - November 1, 2026

Five fresh short articles were labeled by the user before frozen Mac-model predictions were generated; the reference hash was verified unchanged. The language model matched 2/5 and the original BERTopic review-only method matched 3/5. The language model assigned categories to all three user-Unassigned cases. This small sample covers only T002, T004 and Unassigned references and does not support general accuracy claims. It does identify a scope/abstention concern that the earlier development score concealed. Portable-runtime accuracy remains unvalidated. Full local evidence: `review/quick-validation-2026-11-01/report.md`. No database results changed.

## BERTopic primary selection - November 1, 2026

Following user authorization, restored bertopic as the default in registry, adapter, CLI, example and local environment configuration, and deployment files. The semantic implementation remains optional and inactive. Updated the operating guide to distinguish intended five-category definitions from the provisional historical mapping.

Clean Git-eligible export passed 213 tests and 5 subtests, including explicit default-to-BERTopic adapter coverage. A real offline dry-run through the default CLI loaded checksum-verified provisional-v2 and returned T002 for the saved Q004 text; no database access/writes were made by that CLI. Diff formatting checks passed. No model registration, source article, stored assignment, threshold or Git remote was changed. Linux container build/run remains unverified because Docker is unavailable here. Existing review-only Unassigned behavior remains covered by inference/integration tests.

## Required deployment scope clarification

The user confirmed that cloud deployment is not required. Earlier Linux/container acceptance items are optional and do not block the local release. Required remaining assessment concerns local integration, known extraction defects and semantic topic quality; passing software tests does not establish five-category accuracy.

## Final local integration check

104 focused tests and 5 subtests passed. The production frontend built. Real read-only Supabase data passed through local Flask routes; all five topic filters and chart/article counts matched. Isolated Chrome replay of captured API responses passed all five filters and clearing filters with zero page errors. Topic result row count stayed 394. See topic-agent-local-release.md for caveats: no continuous live browser/database session, no pipeline run, and no collection/preprocessing edits. Accuracy remains provisional; cloud deployment is not required.
