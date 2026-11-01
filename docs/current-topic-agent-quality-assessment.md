# Current topic agent: consolidated quality assessment

## Overall judgment

Keep `provisional-v2` as a working baseline. Its pipeline functions, but the available evidence does not establish consistently meaningful groups or reliable article assignments. No replacement tested so far is clearly better. This assessment consolidates saved results; it adds no experiments, model changes, or user-labeling tasks.

## Proposed quality standard

These are practical review criteria, not numeric acceptance thresholds specified by the proposal or approved by a sponsor:

1. **Recognizable theme:** a group's representative and less-central articles share a substantive education theme, rather than only a publisher, place, repeated news event, or writing style.
2. **Honest name:** the readable name describes what the group actually contains. It must not hide mixed subjects behind a precise-sounding label.
3. **Sensible assignments:** unseen articles fit the assigned theme; Unassigned remains available where no theme fits. More assignments alone are not improvement.
4. **Repeatable behavior:** the same article receives the same result when caller batch size or order changes, within the tested environment.

## Evidence and gaps

| Area | Existing evidence | Assessment |
|---|---|---|
| Functional operation | 56 controlled integration checks passed for inference contracts, routing, saving/preservation and dashboard topic data | Supported by automated checks; not a new live browser/database demonstration. |
| Repeatability | Singleton inference gave matching raw/final labels for seven real articles across batch sizes/order and individual calls | Supported for that sample/environment; not a guarantee across library/hardware changes. |
| Recognizable themes | T004's keywords clearly concern cheating, misconduct and detection. Other groups show mixed subjects, publisher/place signals and repeated-event coverage | Partial. Keyword observations suggest influences, not proof of the causal mechanism driving clusters. |
| Names match articles | In a guided review of seven original T003 members, the user retained three as T003, chose two as T002 and one as T005, and rejected one for insufficient detail | Concrete evidence that the original T003 name does not fit all reviewed members. Sequential, disclosed-topic review; not a random accuracy sample. |
| Reviewed assignments | Current singleton model plus fallback matched 23/62 existing human labels; 22 valid-topic articles remained Unassigned and three of five human-Unassigned examples received topics | Substantial errors on selected development examples. Not an overall accuracy estimate or an independent final test. |
| Unseen articles | Paired four-article demonstration: current model left three Unassigned; candidate assigned more but included a questionable campus-administration fit | No clear replacement justified. Assistant interpretation, recent-first sample, different topic taxonomies; no accuracy percentage. |
| Fast T003 correction | One unsupervised three-subgroup NMF diagnostic, excluding the short summary and suppressing selected source terms | Did not separate the six substantive user-reviewed examples; do not apply it. |
| Clearer descriptions | Topic catalog now describes scope and neighboring-topic distinctions | Improves explainability only. Inference does not use those descriptions to choose labels. |

## Decision

The priority is **substantive separation of mixed themes, especially policy, teacher practice and AI literacy within T003**. Merely renaming groups, suppressing a few publisher terms, lowering similarity thresholds or forcing more subgroups has not demonstrated a solution. Do not activate the existing candidates or claim that quality is already improved.

Before another improvement run, choose one change and freeze the comparison: same corpus, same clustering settings, same review examples, and explicit reporting of regressions, Unassigned behavior and source/event concentration. One defensible future question is whether representing entire articles rather than openings improves *unsupervised group coherence*. Earlier full-context supervised experiments did not establish that; they should not be presented as a successful answer. Such a comparison has not been run by this assessment and is not guaranteed to work.

The current baseline should remain reproducible and separately versioned. Existing reviewed examples are development evidence. New-article checks and broader cluster review are still needed before a stronger quality claim; the user is not being asked to create another worksheet.

## Separate proposal-completion items

A direct LDA comparison for the current baseline and a final live integration demonstration remain separate from semantic quality. Existing LDA comparisons used experimental discovery candidates, and passing software tests does not replace quality evaluation.

## Source records

- `docs/topic-review-notes-2026-10-25.md`
- `docs/topic-model-paired-comparison.md`
- `docs/current-topic-quality-review.md`
- `docs/t003-focused-quality-check.md`
- `docs/topic-inference-consistency.md`
- `review/active-single-document-evaluation-2026-10-25/evaluation.json`

No model, catalog, source text, database records or thresholds were changed while preparing this assessment.
