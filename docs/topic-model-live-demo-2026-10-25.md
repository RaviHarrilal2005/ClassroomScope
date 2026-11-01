# Saved topic model demonstration — October 25, 2026

Ran the registered `provisional-v2` model on five existing local article texts. This is inference with a frozen model, not new topic discovery or retraining. No database writes, network model requests, or production code changes occurred.

| Article | Subject | Actual final output |
|---|---|---|
| 5149 | Student survey about AI and learning skills | T001 — AI adoption and learning effects |
| 5241 | Teachers redesigning assignments around AI | Unassigned |
| 5229 | Cheating accusations and AI detection errors | T004 — Academic integrity |
| 5219 | Estonia's student/teacher AI-skills initiative | Unassigned |
| 5231 | Tech newsletter about screen time and general technology | T002 — School AI policy |

Three assigned, two Unassigned. The classroom article's fallback similarity was about 0.8494, just below 0.85; the gap was about 0.0309, above 0.03. Those are similarities, not confidence probabilities. Merely lowering the threshold does not address other misassignments.

## Reproducible consistency concern

Article 5231 previously stayed Unassigned in the six-article assistant assessment. Rechecked using the same loaded model and unchanged text:

- Five-article demo batch: T002.
- Original six-article sample in its original order: Unassigned.
- Article alone: T002.
- Repeated five-article batch: T002.

The raw `original_topic_id` changes too, so this is upstream of the cosine fallback. The evidence establishes sensitivity to batch composition and/or order; it does not isolate the specific library cause. Batch membership and order must be recorded when comparing results. Earlier metrics remain descriptions of their exact batch runs, not guarantees that each article receives the same result in other batches.

This should be investigated before further threshold tuning or deployment. Keep the production model unchanged until a fix can be checked for consistency and semantic regressions.

Local records: `review/model-demo-2026-10-25/results.json` and `batch-check.json`. Prior frozen assistant labels were not altered.
