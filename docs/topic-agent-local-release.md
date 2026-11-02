# BERTopic local baseline - November 1, 2026

## Release scope

The user selected BERTopic as the primary method and confirmed cloud deployment is not required. This records a **functionally checked local prototype baseline**, not acceptance of reliable five-category accuracy. No collection, preprocessing, security or frontend source files were edited during this final check. Upstream extraction defects belong to the responsible teammate and remain a documented dependency.

## Functional evidence

- Clean Git-eligible export previously passed 197 tests and 5 subtests after optional language-model integration was archived.
- Final focused inference, discovery, coordinator/persistence, corpus, dashboard API, topic-count and registry checks passed 104 tests and 5 subtests.
- The frontend production build succeeded. It reported an existing bundle-size advisory; no frontend optimization was performed.
- Read live Supabase data through the actual local Flask results routes without starting the pipeline. Health, all five topic filters, chart counts and article totals matched the read corpus.
- Topic result table rows were 394 before and 394 after the read-only check. No new assignments or historical rewrites occurred.
- The checked dashboard corpus contained 399 articles, 188 with stable topic IDs and 211 without them. The latter includes unassigned/missing topic coverage; it is not a count of successful model rejection decisions.
- The built frontend rendered those captured real API responses in isolated Chrome. All five topic filters and clearing filters produced the expected displayed totals/table row counts, with zero page errors. This combines a real read-only API check with browser response replay; it is not a continuous live browser/database session.
- Screenshot visually inspected: topic chart labels/counts, dropdown and article table rendered. No pipeline/collection controls were invoked.

## Frozen behavior

Default TOPIC_METHOD is bertopic. The trusted saved provisional-v2 model and catalog determine inference; singleton processing and review-only cosine suggestions remain. Outliers stay Unassigned with uncertain_fit. Suggestions do not contribute to assigned counts. Insert-only persistence preserves existing results and their historical provenance. Discovery/training and LDA comparisons are separate deliberate operations. Language-model sources are archived locally and not selectable by the active pipeline.

## Known limits

Historical clusters mix policy, classroom practice and literacy; the intended student-only T001 definition is not fully enforced by the old mapping. Increasing cluster count, averaging whole-article embeddings and the other recorded experiments did not demonstrate a reliable solution. The encoder mainly represents article openings. Model quality remains provisional; passing functional tests does not establish semantic accuracy. Extraction defects are an upstream limitation for the collection/preprocessing owner, not work performed in this release. Cloud/container verification is outside required scope.

## Handoff

Use topic-agent.md for current operations and topic-agent-validation.md for evaluation history. Confirmed human decisions remain in topic-category-review-2026-11-01.md. release manifest: topic-agent-local-baseline-2026-11-01.json. Local detailed API/browser evidence and screenshot are under ignored review/final-local-topic-check-2026-11-01/. No Git commit or push was made by this check.
