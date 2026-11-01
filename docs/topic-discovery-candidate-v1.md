# Proposal-aligned discovery candidate — October 25, 2026

## Run and scope

Trained a new, inactive BERTopic candidate on 318 existing local article bodies, with automatic HDBSCAN discovery (`nr_topics=None`, minimum topic size 10, all-mpnet-base-v2 encoder, seeded UMAP). No five-topic human labels were used to train, exclude, or assign topics. This preserves the proposal's unsupervised-discovery approach.

The source was the existing 322-article snapshot. Four finance/general-news digests (423, 496, 518, 1776) were excluded locally with reasons. Two normalized duplicate copies were among those four exclusions; the remaining 318 texts are unique under case/whitespace normalization. This is targeted contamination cleanup, not comprehensive relevance, source, extraction, or near-duplicate screening. Source text and database rows were not edited.

## Actual training output

Seven topics were discovered; 219 articles (68.9%) were assigned and 99 (31.1%) were Unassigned. These are training-corpus assignments, not held-out inference accuracy.

| Local cluster | Count | Assistant draft interpretation |
|---|---:|---|
| 0 | 52 | Institutional AI adoption and workforce readiness |
| 1 | 45 | Student AI use and learning outcomes |
| 2 | 39 | K–12 AI restrictions and policy debate |
| 3 | 32 | Academic integrity and assessment |
| 4 | 20 | AI literacy, reading and critical thinking |
| 5 | 19 | Classroom AI tools and district implementation |
| 6 | 12 | Educator development and regional AI initiatives |

These are draft labels from keywords and the first three sample excerpts per cluster, not approved names or a full cluster review. Local cluster 0 is not T001, and so on. `label-review.json` retains empty approved-label and stable-ID fields alongside the assistant suggestions and concerns.

## Comparison with traditional LDA

The LDA baseline used the same 318 articles, seven components, 20 batch iterations, and seed 42.

| Descriptive measure | BERTopic | LDA |
|---|---:|---:|
| Keyword diversity (top ten words) | 0.843 | 0.757 |
| Document co-occurrence NPMI | 0.121 | 0.104 |
| Assigned | 219 | 318 |

BERTopic scores higher on these descriptive keyword measures. This does not establish better semantic labels, held-out accuracy, or deployment readiness. LDA forces a topic for every document, whereas HDBSCAN allows Unassigned. BERTopic and LDA use different representations. Adjusted mutual information between their assignments is 0.050; agreement between models is not a correctness measure.

The earlier corpus produced four automatic clusters; removing four texts now yields seven. That demonstrates sensitivity of the discovered structure to corpus changes, not proof that seven is better. Do not compare numeric cluster IDs across these runs as if they represented stable themes.

## Initial review concerns

- The policy cluster's sampled articles repeatedly cover one NYC event; a cluster can reflect repeated news coverage rather than an independent theme.
- The integrity cluster includes a university ChatGPT rollout article among cheating/assessment stories.
- The literacy cluster includes a short podcast summary previously identified as having insufficient substantive detail.
- The smallest cluster has geography, institutional-title and news-writing signals that may be source/style effects rather than a coherent theme.
- Several Unassigned samples still discuss AI education; Unassigned is not an upstream relevance verdict.

## Verification and artifacts

The new model binary was retained, its checksum verified, and it was reloaded successfully. Three training-corpus examples passed singleton inference smoke checks: article 36 → local cluster 3, 45 → cluster 4, 47 → cluster 2. This only verifies loading and execution, not held-out performance. No inference contract changed in this step; the existing suite had 222 passing checks and five subtests after the consistency fix.

Local artifacts (excluded from Git):

- `backend/agents/topic/models/proposal-discovery-v1/`: model binary, topic keywords/counts, assignments, full input snapshot, environment/configuration manifest, review excerpts, and draft label records.
- `review/proposal-discovery-corpus-v1/`: targeted screening manifest, prepared corpus, and inference smoke results.
- `review/proposal-discovery-v1-lda/`: detailed baseline comparison and paired assignments.

The active catalog, original production model, and Supabase data are unchanged. No remote push, external model call, or paid service was used.

## Next decision

Keep this candidate inactive. Complete semantic cluster review and resolve data-quality concerns before registering readable labels and permanent topic IDs. After freezing a candidate and mappings, evaluate assignments on articles outside its training snapshot with consistent singleton inference. The existing 62 reviewed examples overlap this training corpus, so they cannot serve as an independent final test. Prepare a concrete registration/change report before any activation; do not automatically inherit the old five-topic mapping.
