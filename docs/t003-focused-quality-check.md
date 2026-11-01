# Focused T003 grouping check

## Result

One quick attempt did not produce a useful separation. Keep the baseline unchanged; this diagnostic is not a replacement model.

## What was tested

Took the current model's original T003 training group: 27 articles. Excluded article 80 using the user's insufficient-detail decision, leaving 26. Fit a single unsupervised non-negative matrix factorization (NMF) model with three requested subgroups on full-text TF-IDF features. Suppressed the known publisher/geography terms EdSurge and Illinois, plus generic terms, in feature construction only. Article text and preprocessing were not edited. NMF is a traditional topic-modeling method, not a revised BERTopic model.

The requested subgroup count, feature stoplist and method are development choices; no parameter sweep or alternative count search was performed. The user's T002/T003/T005 judgments were not used to fit the model, but were already known during experiment design and used to inspect the result. This is an in-sample diagnostic, not independent validation or a causal test of removing source effects.

## What happened

The 26 articles split into groups of 16, 2 and 8. All six substantive examples from the user's guided review remained together in the largest group:

| Article | User label | New subgroup |
|---|---|---|
| 85 | T003 | 0 |
| 103 | T002 | 0 |
| 104 | T003 | 0 |
| 120 | T005 | 0 |
| 122 | T003 | 0 |
| 124 | T002 | 0 |

The two-article subgroup emphasized a person's name, a place and similar phrasing, so removing two source-associated feature terms did not eliminate other source/style signals. None of the groups was assigned an approved name or a permanent topic ID.

## Decision and scope

Do not apply this result to production. It does not establish that more subgroups or suppressing a few publisher/geography words fixes the mixed policy, literacy and classroom-practice subjects. Topic quality remains unresolved; no successful improvement is claimed.

The current model, topic catalog, thresholds, source text, database records and existing assignments were unchanged by this attempt. The current topic descriptions added in the preceding step remain in place. No additional user labeling is requested.

The exact diagnostic and replay script are local under `review/t003-focused-subgroups-v1/` and excluded from Git. A further improvement attempt should have one explicitly chosen method and an evaluation plan before more training runs, rather than accumulating unvalidated variants.
