# Current model: focused topic quality review

## Scope

The user chose to retain the current registered model as a baseline and requested improved topic quality. This step examined interpretation of its five original groups without retraining, replacing the model, changing thresholds, editing source text, or reassigning database records. The previously requested skip of preprocessing changes was respected.

## Implemented improvement

Added descriptions, examples of included subjects, and boundaries to the five entries in `backend/agents/topic/topic_catalog.json`. Names, stable IDs, model mappings and registered model checksums are unchanged. These are intended topic definitions, not claims that every discovered member fits. The inference code does not read these descriptive fields to choose a topic, so they do not improve assignment accuracy or automatically appear on the dashboard.

| Topic | Intended focus | Distinguish from |
|---|---|---|
| T001 | Student AI adoption and learning/critical-thinking effects | Specific teacher decisions (T003); cheating and detection (T004) |
| T002 | Institutional AI rules, governance, privacy and restrictions | Classroom decisions (T003); AI-literacy instruction (T005) |
| T003 | Teaching practices, assignments, assessment design and classroom AI implementation | Teaching people about AI itself (T005); district policy (T002) |
| T004 | Academic integrity, cheating, plagiarism, detection and misconduct | Broad policy announcements (T002); genuine learning outcomes (T001) |
| T005 | Understanding, evaluating and responsibly using AI | Using AI to teach another subject (T003) |

These boundaries incorporate the guided review: 85/104/122 fit T003, 103/124 fit T002, 120 was judged T005, and 80 lacked sufficient detail. Those review judgments were not applied as new training labels.

## Keyword checks

Recovered all 260 original training article IDs from local snapshots and kept their original cluster assignments. Tested two exploratory descriptions of the same named groups:

1. Class TF-IDF over group text, unigrams/bigrams, alphabetic tokens, frequent-word reduction and a generic reporting-word stoplist.
2. Per-document normalized TF-IDF with sublinear counts and minimum document frequency two; ranked mean weights within the group minus mean weights in other groups. This reduces domination by long articles.

Both are representation experiments, not new cluster models or accuracy evaluations. There was no holdout or objective human relevance score; keyword suggestions were inspected qualitatively. They were not installed into the saved model or used by its fallback.

### Observations

- T004 has recognizable terms: cheating, integrity, misconduct, detection and detectors.
- T002 remains dominated by NYC-policy-event terms, including York City, moratorium and a public official's name. Related coverage may be overrepresented.
- T003's document-balanced keywords include EdSurge, Illinois, leadership, professional and IEP. This suggests publisher/geography/organizational signals, consistent with the mixed policy/practice examples from the guided review. It is evidence of possible source/event effects, not proof that every member was grouped for that reason.
- T005 includes literacy concepts, but also resource-provider and subject-specific terms, consistent with previously identified related stories.
- T001's balanced keywords emphasize colleges, faculty, careers and institutions. Its broad original name may overstate how specifically it represents student learning outcomes.

Simply changing keywords, names or fallback thresholds would not establish that these underlying groups became more coherent. More polished labels can hide rather than repair a mixed cluster, so the existing extracted-keyword behavior was retained.

## Verification and status

Ten saved-model, topic-pipeline and dashboard-count checks passed after the catalog metadata update. Confirmed that the existing names and all model registration data were preserved. The catalog metadata is the only working-agent change in this step; original model and source files remain intact. No model activation, database writes or remote push occurred.

Local review outputs are in `review/current-topic-representation-v1/keyword-proposals.json` and `balanced-keyword-proposals.json`, excluded from Git.

## Recommended next bounded quality task

Investigate T003 as the first source-sensitive cluster, using the already saved user decisions and recorded source-pattern evidence. Choose and validate one grouping improvement in a separate candidate before replacing the baseline. No additional user worksheet is requested. A change to input cleaning is not assumed authorized: the user explicitly deferred that step. Current-model LDA benchmarking and live integration evidence remain separate proposal-completion tasks.
