# Training data revision v2

Status: prepared, not trained. This is a targeted local revision of the 318-article discovery snapshot, following the guided review. It contains 311 article bodies.

## Changes

- Excluded article 80 because the user judged its podcast summary insufficiently substantive.
- Kept one copy of five underlying stories after comparing full-text differences. Excluded 2291 (retained 2290), 531 (retained 530), 2890 (retained 2888), 354 and 356 (retained 351), and 584 (retained 576).
- Differences in those copies were punctuation/formatting, captions, headings, source notices or comment boilerplate, with minor wording variants in the syndicated story. These decisions follow text inspection, not an automatic similarity cutoff. Source URLs are absent from the snapshot, so syndicated provenance was not independently verified.
- Retained articles 85, 103, 104, 120, 122 and 124. The user's alternate topic judgments help evaluate future clusters; they do not make these articles ineligible or supply supervised training labels.

The four finance digests excluded from the previous snapshot remain excluded. Other scope issues identified in the earlier audit have not been silently resolved. This dataset is not claimed to be completely screened or publication-ready.

## Preserved

Retained article text and metadata are unchanged. Original snapshots and all excluded source records remain available in their original local files. The active model, candidate model, catalog, thresholds, evaluation labels and database were not changed. No new model was trained.

## Verification

Confirmed 311 retained records, unique case/whitespace-normalized text, exact preservation of each retained source record, retention of the six substantive guided-review articles, and exclusion of the four previously removed finance digests. Input/output SHA-256 hashes and all keep/exclude reasons are saved in the local manifest.

## Local artifacts

- `review/proposal-discovery-corpus-v2/articles.json`: revised snapshot.
- `review/proposal-discovery-corpus-v2/screening.json`: provenance, hashes, exclusion reasons and prepared-not-trained status.

These local article artifacts are excluded from Git. This short report can be shared without copying the corpus.

The next separate step would be training one candidate on this snapshot with fixed settings. Preparing the dataset does not itself demonstrate better clusters or assignments.
