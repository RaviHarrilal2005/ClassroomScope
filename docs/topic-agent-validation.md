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
