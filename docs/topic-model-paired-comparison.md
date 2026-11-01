# Current model versus candidate: paired four-article demonstration

Ran the current registered model on the same four existing articles previously tested with `proposal-discovery-v2`. Both use singleton inference. The current model retains its existing fallback; the candidate uses raw cluster predictions without a registered fallback. None of the current run's four articles received a fallback assignment. The candidate remains inactive.

| Article | Subject | Current model | Candidate |
|---|---|---|---|
| 12321 | Classroom exercise teaching AI mistakes and source verification | Unassigned | Unassigned |
| 12316 | University AI-tutor partnership conflicts with faculty authority | T001: AI adoption and its effects on learning | Group 1: AI adoption and preparation for future education and work |
| 12312 | Opinion advocating AI automation of university administration | Unassigned | Group 1: AI adoption and preparation for future education and work |
| 12059 | Journalism instruction develops critical thinking in the AI era | Unassigned | Group 2: Student AI use and its effects on learning and critical thinking |

## Interpretation

The candidate adds a plausible learning/critical-thinking assignment for 12059, but also gives 12312 a broad institutional-adoption label despite its focus on university administration rather than student learning or workforce preparation. Both leave the AI-literacy classroom exercise Unassigned. The university partnership article's fit depends on the taxonomy: the candidate's institutional-adoption interpretation is plausible, while the current learning-effects label may not capture the governance focus well.

These are assistant interpretations, not user-confirmed reference labels. Different cluster numbers and names do not themselves indicate mistakes because the two models have different discovered taxonomies. The candidate is not demonstrated to be better on this sample; it makes more assignments, with a tradeoff between useful coverage and questionable fit.

This is a four-article, recent-first demonstration, not representative accuracy validation. Both models' training and earlier reviewed IDs/exact text were excluded in sample selection. Related or syndicated material was not ruled out; lexical similarity screening is only an aid. Article text, including existing extraction clutter, was kept unchanged as requested. No cleaning modifications, database writes, source collection, retraining, catalog updates, model activation or remote push occurred.

Detailed results are saved locally in `review/proposal-v2-unseen-availability/paired-comparison.json` and excluded from Git. Keep the registered model as the working baseline until stronger evidence supports a change.
