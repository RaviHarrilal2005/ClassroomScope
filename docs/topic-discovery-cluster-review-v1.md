# Seven-cluster review — October 25, 2026

## Decision

Do not register or activate this candidate yet. Five groups have recognizable provisional themes; two need substantial corpus or theme review. No readable label or permanent topic ID was approved. This is an assistant review, not sponsor acceptance or an independent accuracy study.

## Scope of inspection

Screened opening excerpts across the 219 assigned articles, the saved first-three review excerpts for each cluster and Unassigned, and overlap with existing human-reviewed labels. The initial combined opening listing was truncated, so cluster 2 was read separately; portions of cluster 1's combined listing were not fully visible. This was not a full-body review of all 318 articles. Existing five-topic labels were used diagnostically after unsupervised training, not to fit or force the clusters. A human-Unassigned label under that catalog does not automatically establish that an article is irrelevant to the broader proposal.

## Proposed names and decisions

| Local cluster | Count | Provisional name | Decision |
|---|---:|---|---|
| 0 | 52 | Institutional AI adoption and campus applications | Needs split/data review: organizational AI, campus administration, professional training and political interview material are mixed. |
| 1 | 45 | Student AI use and learning effects | Recognizable theme; check boundaries with literacy and teaching practice. |
| 2 | 39 | K–12 AI policy and classroom debate | Recognizable but repeated NYC policy coverage dominates; some tutoring and low-content material also appear. |
| 3 | 32 | Academic integrity and assessment | Strong recognizable theme with rollout/policy and teacher-material outliers. |
| 4 | 20 | AI literacy, reading and critical thinking | Recognizable but overlapping; includes a short podcast summary and highly similar reporting. |
| 5 | 19 | Teacher AI implementation and district readiness | Recognizable; distinguish governance announcements from concrete teaching decisions. |
| 6 | 12 | Regional educator-development initiatives | Needs review: geography and news-writing style may be driving the group more than a common subject. |

These labels describe discovered groups; they are not T001–T007 mappings or assertions that every article belongs.

## Concrete concerns

- Cluster 0 includes 283 (organizational AI), 4801 (campus family administration), 5473 (healthcare-management training), and 5822 (broad political interview). Their main subjects and project scope must be examined individually. Do not exclude all university announcements or training articles by format.
- Cluster 2 includes 5225, previously human-reviewed as a request for experiences without substantive responses. This is a content-sufficiency issue despite education vocabulary.
- Cluster 3 includes 264, a university ChatGPT rollout story; mentioning misuse safeguards does not necessarily make integrity its main topic.
- Cluster 4 includes 80, a brief podcast summary previously identified as insufficiently substantive. Format alone is not the exclusion rule.
- Cluster 6's keywords include country names, professional titles and councils. Its small size and mixed sample subjects warrant review before naming it a stable theme.

## Near-duplicate screening

Full-body TF-IDF (unigrams/bigrams, English stopwords, up to 50,000 features) flagged seven pairs at cosine similarity >=0.90:

| Pair | Similarity | Local clusters |
|---|---:|---|
| 2290 / 2291 | 1.000 | 0 / 0 |
| 530 / 531 | 0.997 | 0 / 0 |
| 2888 / 2890 | 0.992 | Unassigned / Unassigned |
| 351 / 356 | 0.991 | Unassigned / Unassigned |
| 576 / 584 | 0.981 | 4 / 4 |
| 354 / 356 | 0.941 | Unassigned / Unassigned |
| 351 / 354 | 0.940 | Unassigned / Unassigned |

Seven pairs are not seven independent extra articles: 351, 354 and 356 form a three-article group. The flags involve eleven article IDs in five connected groups. The threshold was a screening choice, not a validated duplicate detector. Similarity can reflect related coverage; no articles were automatically removed and no database rows were edited. Exact normalized deduplication alone misses punctuation and formatting variants.

## What to do before another training run

1. Resolve these five possible duplicate groups using full text and original URLs, retaining article provenance and a documented keep/exclude decision.
2. Resolve the specific scope and insufficient-content examples. Do not use a missing fixed-topic label as the sole reason for excluding an article from discovery.
3. Obtain source metadata and check approved-source/news criteria. This local snapshot lacks original source names and URLs, so this review cannot establish source eligibility or syndicated origin.
4. Freeze the revised corpus and settings, retrain once, review themes and outliers, then evaluate genuinely unseen assignments before considering registration.

No additional threshold experiments or production changes were made. The candidate binary and raw training outputs remain intact; assistant review decisions were saved in its pending label-review record and under `review/proposal-discovery-cluster-review-v1/`. Approved labels and stable-ID fields remain empty.
