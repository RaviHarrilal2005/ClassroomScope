# Candidate v2: four unseen-article demonstrations

Ran the inactive `proposal-discovery-v2` candidate on four recent existing database articles absent from its 311-article training snapshot and earlier review IDs/exact normalized text. Predictions were computed separately for each article, without the production fallback. No model, mapping, threshold, source record or database result was changed.

| Article | Main subject | Candidate result | Assistant interpretation |
|---|---|---|---|
| 12321 | Teacher uses Google AI summaries to teach hallucinations and source verification | Unassigned | Relevant educational material, but no group clearly captures AI literacy/classroom practice. Needs review; Unassigned alone is not proof of an error in unsupervised discovery. |
| 12316 | University AI-tutor partnership conflicts with faculty rules and authority | Group 1: AI adoption and preparation for future education and work | Plausible institutional-adoption fit, with policy/governance overlap. |
| 12312 | Opinion proposing AI replacement of university administrative work | Group 1: AI adoption and preparation for future education and work | Questionable or broad fit. Main subject is campus administration, not student learning or work preparation. Scope needs review rather than a forced correctness label. |
| 12059 | Teacher argues journalism instruction develops critical thinking in the AI era | Group 2: Student AI use and its effects on learning and critical thinking | Plausible fit, with a teaching-practice emphasis. |

## Interpretation

The candidate can make plausible new-article assignments, but Group 1 may be too broad and educational material can remain Unassigned. These four demonstrations do not establish better performance than the current model: the current model was not rerun on the same four examples for a paired comparison, the sample is recent-first rather than random, and the judgments are assistant interpretations, not independent human labels. No accuracy percentage is claimed.

Assistant notes for the latter three articles were saved before seeing their candidate predictions. The first example was described before inference in chat. The same assistant developed/reviewed this candidate, so the process is not independent-reviewer validation.

Lexical nearest-training similarities ranged from approximately 0.171 to 0.271 using full-body TF-IDF. These are screening aids, not proof that articles have no related or syndicated training material. No original source URLs were checked in this step.

Both university articles contain subscription notices and repeated introductions in the saved clean_content. This is a separate preprocessing issue. The text was deliberately left unchanged for the demonstration; its presence does not establish that it caused either prediction.

## Decision

Keep the candidate inactive. The small sample supplies no basis to replace the current registered model. The next bounded task should examine the input-cleaning issue and the broad institutional-adoption group before further retraining or threshold changes. More user labeling is not requested by this report.

## Local evidence

`review/proposal-v2-unseen-availability/` contains the read-only availability query summary, candidate sample texts, first-example result, pre-prediction notes and three additional results. The availability check read up to 200 recent eligible records and found 30 outside the excluded training/review IDs and exact text. It was not a complete database inventory. Local corpus and raw outputs remain excluded from Git.
