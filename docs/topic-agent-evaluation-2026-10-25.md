# Active topic agent evaluation — October 25, 2026

## Scope

The actual registered `provisional-v2` model was run locally against 62 previously human-reviewed articles. No new worksheet, API key, external model request, or database write was required. These are selected development examples, including samples chosen because the model struggled; the results are not an estimate of accuracy across all incoming articles.

## Results

| Measure | Original model | With active fallback |
|---|---:|---:|
| Matches to human labels | 13/62 (21.0%) | 24/62 (38.7%) |
| Articles assigned a named topic | 15 | 37 |
| Correct among named assignments | 9/15 (60.0%) | 21/37 (56.8%) |
| Valid topic articles left Unassigned | 43 | 22 |
| Human-Unassigned articles given a topic | 1/5 | 2/5 |

The fallback changes 22 predictions and improves net agreement by 11 examples. It recovers valid assignments but also introduces incorrect named assignments. It remains enabled; this evaluation does not change production behavior.

## Results by human label

| Human label | Examples | Original matches | Final matches |
|---|---:|---:|---:|
| T001 | 18 | 1 | 6 |
| T002 | 9 | 2 | 5 |
| T003 | 11 | 0 | 1 |
| T004 | 9 | 6 | 6 |
| T005 | 10 | 0 | 3 |
| U | 5 | 4 | 3 |

## Reproduction and checks

From the project root, with the local reviewed corpus present:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m backend.agents.topic.evaluate_active --output review/active-evaluation-new
```

The output directory must be new. Detailed predictions are saved locally to `evaluation.json`. The evaluator reads the existing review labels and runs the production inference function, including eligibility checks and fallback. It never calls database save functions. Review corpora are excluded from Git; a clean clone needs the local review data restored before this evaluation can run.

All 124 existing backend and saved-model checks passed before cleanup. The active model checksum was verified during real inference.

## Decision for October 31

The integration tests establish functioning software, but this selected sample exposes substantial classification errors. Do not describe the agent as accuracy-validated. Prioritize missed assignments and topic confusion; use a separate fresh assessment before claiming broader quality. If new human labels are skipped, an assistant assessment can identify likely errors, but must be reported separately from human-reviewed validation.

## Repository cleanup

Removed three inactive, unregistered discovery model binaries (1,325,206,135 bytes total), generated Python/test caches, and OS metadata. Kept the registered active model, training manifests, article snapshots, human reviews, prototype source, tests, and migrations. Local review outputs and nested discovery model directories are ignored by Git. No Git history or remote repository was modified.
