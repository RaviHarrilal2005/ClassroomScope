# Fresh topic-training corpus audit — October 29, 2026

## Main finding and next action

Fix article extraction before another training experiment. The current database contains repeated, nested copies of article text, unrelated page content and previously excluded stories. These are observed input defects, rather than a hypothesis that another clustering setting might work.

This audit screened all 349 eligible records in the fresh 2,792-row export. Automated checks were followed by targeted text inspection; this is not a full human subject review of every article. No source text, database record, model or training dataset was changed.

## Findings

### 1. Repeated article text is the highest-priority repair

Twelve records contain at least four substantial text blocks inside their longest block, with redundant contained-word occurrences at least as large as that block. This screen identifies nested/quoted repetition; it does not automatically distinguish legitimate quotations and comments from extractor duplication.

The strongest observed cases are:

| Article | Stored words | Longest block words | Substantial blocks contained in that block |
|---|---:|---:|---:|
| 361 — UNILAG critical-thinking warning | 15,083 | 968 | 31 |
| 1955 — Nigerian AI lesson tool | 12,572 | 825 | 30 |
| 2320 — Nigerian AI-content concerns | 8,435 | 686 | 23 |
| 513 — NYC school AI restrictions | 12,630 | 815 | 32 |
| 1753 — School AI moratoriums | 10,492 | 677 | 32 |
| 2060 — Forum post about AI tutoring | 30,903 | 1,630 | 35 |

Other flagged IDs: 498, 620, 1735, 1925, 1983 and 2065. Some include comments or quotations and need boundary review rather than blanket deletion.

The current extractor collects every paragraph recursively and joins each paragraph's full descendant text. A synthetic nested-paragraph fixture reproduced duplication of the inner paragraph. Stored examples show repeated descending suffixes consistent with this mechanism. Original page HTML was not captured, so the exact markup that produced each record has not been independently established.

**Repair:** extract each content block once, separate article content from comments/navigation, and verify the resulting text against the article. Do not simply truncate every long article to its longest block. Legitimate research papers and transcripts are long too.

Repeated text also compromises interpretation of the whole-article averaging experiment: that method reads the stored repetitions as content. We have not isolated their causal effect on clustering or established that repairing them will resolve topic boundaries.

### 2. Previous screening decisions are not carried into fresh training inputs

All eleven earlier exclusions reappear among the 349 eligible records, with bodies identical to their earlier saved versions:

- Incorrect finance/general-news extraction: 423, 496, 518 and 1776.
- Insufficient summary already rejected by the user: 80.
- Previously reviewed duplicate copies: 354, 356, 531, 584, 2291 and 2890.

423, 496 and 518 have identical normalized bodies despite different education-related titles and different stored hashes. Their bodies concern financial/general news, not the advertised articles. Hash-only deduplication therefore misses a confirmed extraction problem.

**Repair:** preserve reviewed training exclusions and keep/copy decisions in a versioned manifest applied whenever a fresh training snapshot is prepared. The database can retain the source records. Eligibility flags alone are not training-quality approval.

### 3. Two additional syndicated copies should not count as independent stories

Full-text inspection supports these additional training-only copy decisions:

| Retain | Omit extra copy | Evidence |
|---|---|---|
| 2888 | 2889 | Same Velloe hackathon report; extra copy adds publisher history/footer and omits winners. |
| 2930 | 2929 | Same ANI Wayvida report; 2929 appends Tribune history/footer. 2930 contains the story without that material. |

These are assistant-reviewed content comparisons. URL metadata supports the syndicated context; the live source pages were not fetched. Decisions remain recommendations, not applied exclusions.

The full similarity screen produced fourteen candidate pairs, including known duplicates and a same-title/different-body mismatch. Similarity thresholds are screening aids, not automatic deletion rules.

### 4. Some successful extractions contain little of the advertised article

Article 11051, about a teenager's AI startup, contains only 100 words: a caption followed by unrelated election, inflation, property and banking headlines. It passes the existing 80-word extraction minimum. Hold it out of training until the actual article body is recovered.

Articles 5167 and 5225 solicit reader experiences without supplying the responses. Article 11175 is a conference roundup linking to other articles. These need substantive-content review; short length alone is not a reason to reject an article.

Subscription/account markers appeared in 14 records, copyright/footer markers in 19, and exact repeated paragraphs in 18. In total, 85 records triggered at least one initial lexical/length/repetition flag. Flags overlap and are not 85 confirmed bad articles. Fourteen texts exceed 6,000 words and 27 are below 300; neither length category is automatically invalid.

### 5. Scope and balance require honest treatment

Potential scope questions include healthcare-management training (5473), university administration automation (12312), a university opening with AI degrees (11086), and a convocation speech with a secondary AI warning (11965). These should be assessed against the proposal's discovery scope. A mismatch with the current five-topic catalog does not by itself justify excluding an article from unsupervised discovery.

Source concentration is measurable: Guardian, eSchool News and EdSurge domains supply 120/349 records (34.4%). Fourteen titles match a broad NYC school-policy screen, including the already-invalid extraction 518; this is a candidate repeated-event set, not fourteen verified duplicate stories. Distinct reporting and opinions should not be collapsed just because they cover one event.

True topic imbalance cannot yet be measured: the 349 records do not have a complete, independently reviewed topic inventory. Publisher counts and model-generated clusters are not a substitute. Review coverage before imposing arbitrary equal topic counts.

## Concrete order of work

1. Repair and test the extractor's repeated-descendant-text behavior. Check article/comment boundaries and unrelated-page fallback behavior.
2. Produce locally corrected text for affected records, with before/after evidence. Preserve original text and metadata; validate that substantive paragraphs survive.
3. Prepare a fresh training snapshot that applies the eleven previous decisions, the two additional reviewed copy decisions and the confirmed failed-extraction hold. Record unresolved scope/content cases separately.
4. Assign story-family groups before splitting development and evaluation data so syndicated copies and closely related reporting do not leak across the split. Previously reviewed examples are development evidence, not a fresh final test.
5. Only then run one controlled training comparison. Report quality and coverage changes; repair work alone is not proof of better assignments.

The 38 eligible IDs outside the earlier 311 consist of eleven restored exclusions and 27 other IDs. They are not all newly collected or untouched evaluation material. No new model was trained during this audit.

## Evidence

Local outputs under `review/corpus-audit-fresh-2026-10-29/` include the full inventory, input checksum, similarity candidates, extraction flags, contained-text evidence, the extractor reproduction and reviewed recommendations. The source snapshot remains under `review/database-articles-2026-10-29-fresh/`. Article bodies and local review artifacts remain excluded from Git.
