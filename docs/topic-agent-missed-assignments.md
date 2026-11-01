# Missed assignment investigation — October 25, 2026

The active agent leaves 22 human-topic articles Unassigned in the 62 previously reviewed examples. These misses include tutoring and learning effects, student AI-use surveys, literacy resources, classroom experiences, and detector reliability. The registered encoder only sees the first 384 tokens. However, several missed articles state their subject in their opening, so truncation alone does not explain the failures. Mixed nearest-neighbor labels also expose overlapping topic boundaries.

## Tested approaches

A full-body TF-IDF classifier trained with held-out text groups and a fixed probability requirement of 0.60 plus a 0.15 margin produced no rescues. Its output remains local under `review/missed-rescue-v1`; the unsuccessful implementation was removed.

The new `neighbor_rescue.py` proposes a topic only when the three nearest distinct reviewed article groups agree on a named topic and each has cosine similarity at least 0.65. It excludes the evaluated article and every normalized-text duplicate. Existing named assignments are preserved. It uses verified cached encoder vectors and current corrected labels, without keys or database access. Similarities are not confidence probabilities. The 0.65 cutoff is experimental and uncalibrated; no threshold sweep was conducted.

| Measure | Active agent | Experimental rescue |
|---|---:|---:|
| Correct matches | 24/62 | 28/62 |
| Human-topic articles left Unassigned | 22 | 17 |
| Correct among assigned | 21/37 (56.8%) | 25/42 (59.5%) |
| Human-Unassigned articles assigned a topic | 2/5 | 2/5 |

Five proposals are made. Four match the existing human labels: article 5233 and 5245 → T004; articles 5226 and 5131 → T001. Article 5134 is incorrectly proposed as T001 instead of the human label T003. Thus the reduction from 22 to 17 misses includes one wrong topic, not five successful corrections.

## Status

The rescue remains inactive because it still confuses classroom practice with learning effects, and only five negative examples are available. It provides inspectable proposals, not an automatic production fix. The active agent, model registration, thresholds, and database records are unchanged. Both experiments use development data; neither establishes fresh-data accuracy. The approach was selected after prior experiments on the same corpus, so held-out predictions do not remove the broader development-selection bias.

## Reproduce

Run from the project root with the local review corpus and cached vectors restored:

```bash
.venv/bin/python -m backend.agents.topic.neighbor_rescue \
  --cache review/topic-candidate-v2 \
  --baseline review/active-evaluation-2026-10-25/evaluation.json \
  --output review/neighbor-rescue-new
```

The output directory must be new. Detailed proposals and their three supporting article IDs are recorded in `evaluation.json`. No additional worksheet is created. Local corpus and evaluation outputs remain excluded from Git.
