# Revised-data training result

Trained `proposal-discovery-v2` on the revised 311-article snapshot. Training completed successfully. The candidate is saved locally and remains unregistered and inactive.

| Measure | Previous candidate | Revised-data candidate |
|---|---:|---:|
| Training articles | 318 | 311 |
| Automatically discovered topics | 7 | 5 |
| Assigned articles | 219 | 250 |
| Unassigned articles | 99 | 61 |

The full recorded training settings match the previous candidate. Five topics were discovered automatically; five was not requested. Input changes can substantially change cluster structure. Fewer Unassigned articles and fewer clusters do not establish improved semantic quality or accuracy. The corpus differs, so raw totals are not a paired performance comparison. Topic numbers must not inherit the current T001–T005 mapping.

Verified successful training status, the saved model's SHA-256 checksum, 311 distinct article assignments, and 61 Unassigned rows. This step did not reload the saved model or evaluate new-article accuracy. Keywords and pending label-review records were generated for later inspection. No labels have been approved.

Local files are under `backend/agents/topic/models/proposal-discovery-v2/`: model binary, snapshot, training manifest, topic keywords/counts, assignments, sample excerpts, and pending label-review records. These are excluded from Git. Source revision details are in `docs/topic-training-data-revision-v2.md`.

The current registered model, catalog, inference code, thresholds, database and historical results were unchanged. No activation or remote push occurred.

The next separate step is reviewing the five discovered groups before deciding whether this candidate is better.
