# Topic agent implementation checklist

As of November 1, 2026. Design decisions are documented; model acceptance and the items below remain separate work. See `topic-agent-design.md` for contracts and `topic-agent-validation.md` for evaluation.

## Completed in this design session

- [x] Retain five reporting categories and define student-only T001.
- [x] Review selected boundary examples from all five historical clusters and save confirmed labels separately from historical results.
- [x] Keep initially Unassigned model results Unassigned; retain review-only suggestions.
- [x] Verify review-only behavior with existing inference, storage integration and count tests (10 passed).
- [x] Agree three Unassigned reasons: insufficient content, outside the five groups and uncertain fit.
- [x] Document deliberate discovery, review and activation, preserving historical results.
- [x] Document validation and distinguish development evidence from independent evaluation.

## Implementation before alignment sign-off

- [ ] Review/replace the active T001 mapping and historical reference examples against student-only scope. Updating descriptions alone does not change semantic decisions.
- [ ] Permit multiple discovered clusters to map to a category; verify registry validation, fallback suggestions and downstream counts.
- [ ] Support explicitly unmapped model topics without failure; leave results Unassigned with Uncertain fit. Review mapping before activation.
- [x] Emit `uncertain_fit` for model outliers and null for assigned results; prepare nullable database fields.
- [ ] Apply `20261101000100_topic_result_provenance.sql` before live inference; verify storage.
- [ ] Add explicit scope/content checks or reviewed decisions before using the other reasons. Empty inputs are currently skipped.
- [x] Emit a SHA-256 mapping/definition/label reference; historical rows are preserved. Live storage awaits migration application.
- [ ] Preserve training exclusions and copy decisions in a versioned manifest; repair and verify extraction issues before new training.
- [ ] Evaluate a separately frozen model/assignment change capable of separating mixed cluster members. Do not promote optional local classifiers without independent evidence; retain unsupervised discovery.

## Evidence before activation

- [ ] Run fresh independently labeled article evaluation, including all categories and Unassigned cases.
- [ ] Measure the new review-only baseline under current definitions; do not reuse earlier fallback accuracy claims.
- [ ] Complete and document the applicable same-corpus LDA comparison.
- [ ] Complete controlled live database/dashboard demonstration.
- [ ] Record acceptance criteria, limitations and explicit activation decision.

## Optional later work

- Review queue and approval UI. Suggestions are currently stored fields, not an operational human-review workflow.
- Replacement reprocessing with version history and a clear dashboard selection policy. Existing storage preserves old article rows.
