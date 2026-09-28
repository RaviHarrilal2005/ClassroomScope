# INTERFACE.md — Classification Subsystem

**Owner:** Juan Reyes
**Consumers:** Orchestrator (Ravi), Results Aggregator, Web Dashboard
**Last updated:** September 28, 2026
**Status:** Complete and tested in isolation. Ready for orchestration integration.

## 1. Purpose

This document defines the callable interface of the Classification
subsystem (WBS 5.9, 5.10) so the Orchestrator can sequence it inside
the full pipeline. It covers function signatures, database contracts,
preconditions, and postconditions.

## 2. Dependency on Collection

Classification runs AFTER the Collection subsystem has populated
`articles` with `is_relevant = true` AND `processing_status = 'success'`.

If those conditions aren't met, both classifiers run cleanly but
find zero rows to process. No errors, no wasted API calls.

## 3. Two classifiers (F.10 comparison)

This subsystem implements two independent classifiers that write to
the same table distinguished by a `classifier` tag:

| Classifier | Module | Method | Tag |
|---|---|---|---|
| Baseline | `classify_baseline.py` | Keyword counting | `baseline_keyword` |
| LLM | `classify_luna.py` | GPT-5.6-Luna (zero-shot) | `gpt-5.6-luna` |

Both output the same three fields: stakeholder category, source
type, and confidence scores. This enables the F.10 comparison
deliverable — a direct agreement matrix between traditional NLP
and LLM-based classification.

## 4. Function contracts

### 4.1 `classify_baseline.run(limit=None)`

**Signature:**
```python
def run(limit: int | None = None) -> dict

Arguments:

limit — max articles to classify, or None for all pending

Returns:

python
{"classified": int, "skipped_existing": int, "failed": int}
Side effects: Inserts rows into classification_results with
classifier = 'baseline_keyword'.

Preconditions: Rows exist with is_relevant = true AND
processing_status = 'success' AND no existing
classification_results row for this classifier and article.

Idempotent: Yes — queries existing classifications and skips
already-processed articles.

Rate limiting: None. Pure local text processing.

4.2 classify_luna.run(limit=None)
Signature:

python
def run(limit: int | None = None) -> dict
Arguments:

limit — max articles to classify, or None for all pending

Returns:

python
{"classified": int, "skipped_existing": int, "failed": int}
Side effects: Inserts rows into classification_results with
classifier = 'gpt-5.6-luna'.

Preconditions: Rows exist with is_relevant = true AND
processing_status = 'success' AND no existing
classification_results row for this classifier and article.

Idempotent: Yes.

Rate limiting: Sleeps 0.3 seconds between API calls. On 429,
increase to 1 second and re-run (safe).

External dependency: FAU Trussed AI portal endpoint
(TRUSSED_BASE_URL and TRUSSED_API_KEY in .env).

5. Database contract — classification_results
Read by: classify_baseline (skip check), classify_luna (skip
check), Analysis Agents, Dashboard
Written by: classify_baseline (INSERT), classify_luna (INSERT)

Column	Type	Notes
id	bigint PK	auto
article_id	bigint FK	→ articles.id
stakeholder_category	text	students / educators / administrators / policymakers / parents / researchers / undetermined
confidence	float	0.0–1.0
source_type	text	news_outlet / trade_publication / academic / government / blog
source_type_confidence	float	
classifier	text	'baseline_keyword' or 'gpt-5.6-luna'
classified_at	timestamptz	
Unique constraint: (article_id, classifier) — one row per
article per classifier.

6. Category definitions
6.1 Stakeholder categories
The stakeholder category is who the article is primarily about
(not who wrote it, not who it is written for).

Category	Definition
students	Article's primary subject is student experience, learning, or behavior
educators	Primary subject is teaching, instruction, or faculty practice
administrators	Primary subject is institutional leadership, deans, policy implementation
policymakers	Primary subject is regulation, legislation, or government action
parents	Primary subject is family or parental concerns
researchers	Primary subject is academic study or research findings
undetermined	No clear single subject, or confidence below threshold
6.2 Source types
Assigned by domain lookup (same mapping in both classifiers).

Source type	Examples
news_outlet	edweek.org, insidehighered.com, nytimes.com
trade_publication	eschoolnews.com, educationdive.com
academic	.edu domains
government	.gov domains
blog	default fallback
7. Integration notes for the Orchestrator
Return summary dicts. The run() functions currently print
to stdout. Signatures above show the recommended return shape.

Run both classifiers sequentially. They write to the same
table but with different classifier tags. Running them in
parallel risks duplicate-work on the same articles.

No dependency between the two classifiers. They don't read
each other's output. Order of execution doesn't matter.

8. F.10 comparison query
To produce the baseline ↔ LLM agreement matrix:

sql
SELECT
    b.stakeholder_category AS baseline,
    t.stakeholder_category AS luna,
    COUNT(*) AS n
FROM classification_results b
JOIN classification_results t
    ON b.article_id = t.article_id
WHERE b.classifier = 'baseline_keyword'
  AND t.classifier = 'gpt-5.6-luna'
GROUP BY 1, 2
ORDER BY n DESC;
9. Known limitations
Baseline "students" bias. Keyword classifier over-selects
"students" because it's a high-frequency word in education text
regardless of article subject. Confirmed via manual review of
disagreement cases.

Prompt injection surface. classify_luna passes raw article
text to the LLM. Current mitigation: 8,000-char truncation and
a JSON-only system message. Full sanitization is owned by the
Security subsystem (Section 2.9).

No transformer fallback. If the Trussed endpoint is down,
classify_luna fails cleanly but the classification set is
incomplete. Re-running later resumes where it left off.

10. Current state (as of Sept 28, 2026)
Articles classified (baseline): 248

Articles classified (gpt-5.6-luna): 248

Baseline ↔ Luna agreement: 50.8%

Top agreements: students (81), educators (41)

Top disagreements: students↔educators (48), students↔administrators (31)
