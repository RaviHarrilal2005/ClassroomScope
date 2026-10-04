# Topic quality review — provisional-v2

## Scope

Reviewed the saved representative excerpts for 15 training-sample records and checked their current assignments against the new 260-row export. Twelve remain assigned to their original topics. Three are now Unassigned and are not counted as evidence for current assigned-topic quality. No investigation of the Unassigned rate was performed.

This is a qualitative spot check, not a random-sample accuracy estimate or a full-corpus validation. Evidence comes from previously saved excerpts, not fresh full-article retrieval. Factual claims, publication authenticity, and public accessibility were not independently verified.

## Findings by topic

| Stable ID | Label | Current matching samples | Assessment |
|---|---|---:|---|
| T001 | AI adoption and its effects on learning | 2 | Supported but broad |
| T002 | School AI restrictions, privacy, and policy | 3 | Supported in sampled coverage |
| T003 | Classroom AI implementation and teacher practice | 3 | Supported with overlap |
| T004 | Academic integrity, cheating, and AI detection | 3 | Supported in sampled coverage |
| T005 | AI literacy and educational resources | 1 | Limited current sample |

### T001

Adoption and learning impacts cover the reviewed texts. Article 2223 focuses on university teachers’ intention to keep using GenAI; article 918 mixes predictions about teaching, learning, administration, and adoption. Both still have T001 in the new export.

Keep the provisional label. Treat T001 as broad adoption/learning coverage; distinguish hands-on implementation from T003.

### T002

Articles 523, 1753, and 513 discuss school restrictions or moratoria, student privacy, safeguards, and exceptions. All three remain T002. Their shared coverage of reported school-policy events limits event diversity.

Keep the label. Keywords such as com, 2026, city, and york are weak theme descriptors; record this for the next deliberate model revision, without editing the registered model.

### T003

Articles 747, 120, and 916 cover teacher workflows, implementation guidance, school culture, and district-wide adoption. All three remain T003. Article 120 also includes integrity and governance; article 916 includes broad predictions beyond classroom practice.

Keep the provisional label. Define T003 around implementation and teacher practice; flag broad trend pieces for human review where T001 overlaps.

### T004

Articles 2228, 1983, and 1732 focus on detection, academic-integrity rules, or AI-assisted cheating. All three remain T004. This sample includes a research paper and a first-person course-policy account, so it is not exclusively news reporting.

Keep the label. Record source types separately so research and personal accounts do not stand in for independent news coverage.

### T005

Article 584 describes school AI-literacy training and learning the limitations of generative AI; it still has T005. Articles 576 and 256 were training representatives but are Unassigned in the new export. Articles 584 and 576 contain near-identical coverage, so they do not supply independent evidence.

Keep the label provisionally. Review additional distinct currently assigned T005 articles before treating the topic as validated.

## Sample assignment check

| Article ID | Training topic | Current exported assignment | Used for current-topic review |
|---|---|---|---|
| 2223 | T001 | T001 | Yes |
| 918 | T001 | T001 | Yes |
| 361 | T001 | Unassigned | No |
| 523 | T002 | T002 | Yes |
| 1753 | T002 | T002 | Yes |
| 513 | T002 | T002 | Yes |
| 747 | T003 | T003 | Yes |
| 120 | T003 | T003 | Yes |
| 916 | T003 | T003 | Yes |
| 2228 | T004 | T004 | Yes |
| 1983 | T004 | T004 | Yes |
| 1732 | T004 | T004 | Yes |
| 584 | T005 | T005 | Yes |
| 576 | T005 | Unassigned | No |
| 256 | T005 | Unassigned | No |

## Practical interpretation

Keep the five labels provisional. T002 and T004 have clear thematic fit in the reviewed samples. T001 and T003 are broader and overlap; a single assignment describes the dominant model cluster, not every theme in an article. T005 has only one matching current representative in this saved sample.

News remains the primary project corpus. The sampled research paper and first-person account should be distinguishable from news through source classification. This review collected no additional sources, Reddit posts, or social media data. It does not certify that the existing corpus meets all source rules.

No labels, keywords, model files, catalog mappings, database assignments, or collection-cleaner code were changed. For the next development step, connect the real topic results to dashboard counts and filters while retaining an explicit Unassigned category.

## Evidence files

- Current export: `/Users/esme/Downloads/topic_results_rows.csv`
- Saved excerpts: `topic_model_agent/models/provisional_v2_review.md`
- Identity and labels: `topic_model_agent/topic_catalog.json`
