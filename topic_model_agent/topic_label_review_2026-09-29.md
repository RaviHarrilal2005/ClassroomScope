# Topic label review — September 29, 2026

These labels were agreed during a manual review of database exports. They are
review notes for the observed groups, not permanent mappings from topic numbers
to names. No database records or model settings were changed during this review.
The exports do not contain a model run ID, so their common run provenance cannot
be independently verified. Group numbers were traced from the earlier review
CSV and the observed automatic labels.

## Agreed labels

| Group | Observed automatic label | Reviewed label | Status |
| --- | --- | --- | --- |
| 0 | City / Framework / Trends | AI adoption and policies in schools | Tentative; broader review needed |
| 1 | Academic integrity and assessment (group 1) | Academic integrity and assessment | Mixed; further review needed |
| 2 | COVID / Awareness / Edtech | General education and school operations | Mixed; relevance review needed |
| 3 | Financial / Enrollment / Barrow | Education access, finances, and governance | Mixed; relevance review needed |
| 4 | Academic integrity and assessment (group 4) | Critical thinking and AI dependence | Tentative; broader review needed |

## Evidence and limitations

- **Group 0:** Articles 57 and 103 concern school AI restrictions and policy.
  Article 351 concerns privacy safeguards. Articles 85 and 500 concern classroom
  adoption and AI literacy resources, motivating the broader wording.
- **Group 1:** Articles 36 and 107 support academic integrity and assessment.
  Article 497 overlaps with policy. Articles 58 and 67 concern certificates and
  workforce preparation, demonstrating mixed themes.
- **Group 2:** Articles 246, 736, and 770 concern social media during COVID,
  teacher recruitment, and facilities leadership. Articles 727 and 762 discuss
  cybersecurity and teacher development with some AI content. The group does
  not establish a coherent generative-AI-in-education theme.
- **Group 3:** Articles 655, 659, and 646 concern enrollment, student finances,
  and disability access. Article 657 concerns governance. Article 100 concerns
  career preparation in an AI-shaped economy. The broad label does not resolve
  the mixed content or establish project relevance for every article.
- **Group 4:** Articles 90, 289, and 454 support critical thinking and AI
  dependence. Article 31 covers broader learning outcomes. Article 620's excerpt
  fits, but its extracted text includes a discussion thread that needs cleaning.

This was a qualitative sample review, not a measured accuracy evaluation.
Unassigned articles were not given a theme label. A readable name does not fix
incorrect groupings or irrelevant inputs.

## Source snapshots

- `/Users/esme/Downloads/Supabase Snippet Article Content by Topic.csv`:
  100 rows, including 37 for group 0, 44 for group 1, and 19 for group 4.
  Group 0 coverage is partial compared with the earlier review export.
- `/Users/esme/Downloads/Supabase Snippet Article Content by Topic (1).csv`:
  52 rows, including 28 for group 2 and 24 for group 3.
- Earlier `topic_review_20260929T181111877035Z.csv`: inspected previously,
  but no longer available at its supplied path during the walkthrough.

## Next review

After preprocessing corrections, rerun with the same model settings and review
the new clusters. Reuse a label only when the new article content supports it;
do not automatically transfer these labels by numeric topic ID. Preserve raw
labels, keywords, source article IDs, and a run identifier with future reviews.
