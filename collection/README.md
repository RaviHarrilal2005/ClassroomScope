# README.md — Collection & Preprocessing Subsystem

**Owner:** Juan Reyes\
**Consumers:** Orchestrator (Ravi), Analysis Agents, Security Subsystem\
**Last updated:** October 8, 2026\
**Status:** Complete and tested in isolation. Guardian source + comment
retrieval added. Ready for orchestration integration.

## 0. Changelog since Oct 3, 2026

- Added `guardian_fetcher.py` — Guardian Open Platform article source.
- Added `guardian_comments.py` — comment retrieval via the Guardian
  Discussion API.
- Added two columns to `articles`: `guardian_discussion_key`,
  `guardian_commentable`.
- Added `comments` table.
- **Pipeline reorder:** comments now run AFTER preprocess, gated on
  `llm_relevant = true` AND `processing_status = 'success'`.
- **Deprecated:** `ingest_reddit.py` and the Reddit corpus. Sponsor
  ruled the social-media workaround out of scope (news sources only).
  Reddit tables are retained but dormant — no runtime code reads them.

## 1. Purpose

This document defines the callable interface of the Collection and
Preprocessing subsystem (WBS 4.9, 4.10) so the Orchestrator can
sequence it inside the full pipeline. It covers function signatures,
database contracts, preconditions, and postconditions for each stage.

## 2. Pipeline stages (ordered)

The subsystem exposes four stages. The Orchestrator runs them in
this order:

1. **fetch** — pull article metadata from APIs and RSS feeds
2. **store** — normalize + dedup + insert into `articles`
3. **keyword filter** — mark candidate relevant articles (F.3, recall)
4. **LLM verify** — confirm relevance with GPT-5.6-Luna (F.3, precision)
5. **preprocess** — fetch full article text, extract body (F.5)
6. **comments** — fetch Guardian comments for articles that survived
   the article branch (stages 1–5)

Stage 3 is deliberately permissive (recall); stage 4 applies precision.
Stage 5 gates on `llm_relevant = true`. Stage 6 gates on both
`llm_relevant = true` AND `processing_status = 'success'` AND
`guardian_commentable = true`.

**Sequencing note:** comments run last, after preprocess. They attach
to articles that are actually in the analysis corpus. Earlier versions
pulled comments for commentable-but-irrelevant articles; that's fixed.


Each stage is idempotent. Re-running never produces duplicates and
never corrupts prior results.

## 3. Module inventory

| Module | Stage | Primary function |
|---|---|---|
| `fetchers.py` | fetch | `fetch_from_newsapi`, `fetch_from_gnews`, `fetch_from_rss` |
| `guardian_fetcher.py` | fetch | `fetch_from_guardian` |
| `db.py` | store | `insert_articles(articles)` |
| `filter_relevance.py` | filter | `run()` |
| `llm_verify_relevance.py` | LLM verify | `run(limit=None)` |
| `preprocess.py` | preprocess | `run(limit=None)` |
| `guardian_comments.py` | comments | `run(limit=None)`, `fetch_comments_for(article_id, key)` |
| `ingest_reddit.py` | (deprcated) | `ingest(path, source)` |

## 4. Function contracts

### 4.1 `fetchers.fetch_from_*`

**Signature:**
`def fetch_all() -> list[dict]`

**Returns:** A list of raw article dicts:

```
{
    "title": str | None,
    "author": str | None,
    "published_date": str | None,   # ISO 8601 or RFC 822
    "source": str | None,            # outlet name
    "url": str,                      # required
    "content": str,                  # summary or truncated body
}
```

**Side effects:** None. Pure fetch.

**Behavior:** Calls NewsAPI, GNews, and RSS feeds internally.\
Loops through configured search queries. Rate-limit aware.\
Individual source failures are caught and logged; returns partial
results rather than raising.

### 4.2 `guardian_fetcher.fetch_from_guardian(max_pages=10, page_size=50)`

**Returns:** list of article dicts in the shared shape, plus two
Guardian-specific keys:

```
{
    "title": str | None,
    "author": str | None,
    "published_date": str | None, # ISO 8601
    "source": "The Guardian",
    "url": str, # canonical web URL
    "content": str, # trailText (summary, not body)
    "guardian_discussion_key": str | None, # "/p/xxxxx" or None
    "guardian_commentable": bool # Guardian flag at fetch time
}
```

**Side effects:** none. Pure fetch.

**Query:** a single boolean query against `tag=education/education`:
q = '"generative AI" OR "gen AI" OR "large language model" OR
ChatGPT OR Gemini OR Claude OR Copilot'

**Ordering:** `order-by=newest`, deliberate. `relevance` would return
the same top articles every run and dedup would skip them.

**Failure mode:** partial results, never raises. Individual page
failures break the loop and return what was collected.

### 4.3 `db.insert_articles(articles)`
**Signature:**
`def insert_articles(articles: list[dict]) -> tuple[int, int]`

**Arguments:**
- `articles` — output of `fetch_from_*`

**Returns:** `(inserted_count, skipped_count)`. Rows whose URL
already exist are counted as skipped.

**Side effects:** Writes to `articles` table using
`upsert(on_conflict="url", ignore_duplicates=True)`.

**Notes:**
- Requires RLS INSERT policy on `articles` (present)
- Requires `anon` role to have GRANT INSERT, SELECT on `articles`
- Date normalization happens inside this function via `_parse_date`

### 4.4 `filter_relevance.run()`
**Signature:**
`def run() -> dict`

**Returns:**
`{"checked": int, "relevant": int, "irrelevant": int}`

**Side effects:** Updates `articles.is_relevant` for rows where
`is_relevant IS NULL`. Never overwrites an existing flag.

**Preconditions:** Rows exist with `is_relevant IS NULL`.

**Postconditions:** Every row has `is_relevant` set to `true` or
`false`.

**Idempotent:** Yes.

### 4.5 `llm_verify_relevance.run(limit=None)`
**Signature:**
`def run(limit: int | None = None) -> dict`

**Arguments:**
- `limit` — max articles to verify, or `None` for all pending

**Returns:**
`{"verified": int, "kept": int, "dropped": int, "failed": int}`

**Side effects:** Updates `articles.llm_relevant`, `articles.llm_relevance_reason`, `articles.llm_verified_at`.

**Behavior:** For each article where `is_relevant = TRUE` and `llm_relevant IS NULL`, sends title + first 2,000 chars of content to GPT-5.6-Luna. Model returns a strict binary verdict with one-sentence justification. Result is stored as `llm_relevant`.

**Preconditions:** Rows exist with `is_relevant = TRUE` AND `llm_relevant IS NULL`.

**Postconditions:** Those rows have `llm_relevant` set to `TRUE` or `FALSE`, with reason and timestamp.

**Idempotent:** Yes.

### 4.6 `preprocess.run(limit=None)`
**Signature:**
`def run(limit: int | None = None) -> dict`

**Arguments:**
- `limit` — max articles to process, or `None` for all pending

**Returns:**
`{"processed": int, "success": int, "failed": int, "paywalled": int}`

**Side effects:** Updates `articles.clean_content`,
`processing_status`, `processing_note`, `processed_at`.

**Preconditions:** Rows exist with `llm_relevant = TRUE` AND
`processing_status = 'pending'`.

**Postconditions:** Those rows have `processing_status` in
`{'success', 'failed', 'paywalled'}`.

**Rate limiting:** Sleeps 1 second between fetches. Do NOT run
concurrently on the same source domain.

**Idempotent:** Yes — only processes `pending` rows.

### 4.7 `guardian_comments.run(limit=None)`

**Returns:** none currently (prints a summary). Should return a dict
when the Orchestrator wires it in.

**Side effects:** upserts rows into `comments`.

**Preconditions:** rows exist where
`guardian_commentable = TRUE` AND `llm_relevant = TRUE` AND
`processing_status = 'success'` AND no rows already exist in
`comments` for that `article_id`.

**Behavior:** for each qualifying article, calls
`fetch_comments_for(article_id, discussion_key)`, then upserts in
batches of 100 on `comment_id`.

**Idempotent:** yes — skips articles already in `comments`.

### 4.8 `guardian_comments.fetch_comments_for(article_id, discussion_key)`

**Signature:** `def fetch_comments_for(article_id, discussion_key) -> list[dict]`

**Returns:** normalized comment rows ready for `comments` upsert.
Returns `[]` on any failure; never raises.

**Behavior:** paginates top-level comments via the Guardian Discussion
API. Replies arrive embedded under each top-level comment's
`responses` field, so no extra requests. Recursion via `_flatten()`
collects nested replies.

**Skips:** comments with `status != 'visible'` (moderator-removed).
Descends into their `responses` in case any replies are visible.

### 4.9 `ingest_reddit.ingest(path, dataset_source)`
**Signature:**
`def ingest(path: str, dataset_source: str) -> None`

**Arguments:**
- `path` — file path to a semicolon-delimited CSV
- `dataset_source` — label written to `dataset_source`, e.g. `'dataset_1'`

**Side effects:** Writes to `reddit_posts` and `reddit_comments`.
Posts first (FK requirement). Orphan comments filtered before insert.

Not part of the runtime pipeline. One-time import only.

## 5. Database contract — `articles`
**Read by:** filter_relevance, preprocess
**Written by:** db.insert_articles (INSERT), filter_relevance
(UPDATE is_relevant), preprocess (UPDATE clean_content + status)

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | auto |
| title | text |  |
| author | text | nullable |
| published_date | timestampz | nullable |
| source | text | outlet name |
| url | text UNIQUE | dedup key |
| content | text | raw summary/truncated |
| content_hash | text | informational only |
| is_relevant | boolean | NULL until filter runs |
| llm_relevant | boolean | LLM filter verdict (final gate |
| llm_relevance_reason | text | LLM justification |
| llm_verified_at | timestampz | |
| clean_content | text | NULL until preprocess succeeds |
| processing_status | text | 'pending' / 'success' / 'failed' / 'paywalled' |
| processing_note | text | failure reason |
| processed_at | timestampz | |
| collected_at | timestampz | |
| **guardian_discussion_key** | **text** | **Guardian only. e.g. '/p/x5379f'. NULL otherwise.** |
| **guardian_commentable** | **boolean** | **Guardian only. True at fetch time. NULL otherwise.** |

**Row state flow:**
```
INSERT          → is_relevant=NULL, llm_relevant=NULL, processing_status='pending'
keyword filter  → is_relevant=TRUE/FALSE
LLM verify      → llm_relevant=TRUE/FALSE (only on keyword=TRUE rows)
preprocess      → processing_status in {success, failed, paywalled}
                  (only on llm_relevant=TRUE rows)
comments        → rows in comments (only on llm_relevant = TRUE AND processing_status = 'success'
                  AND guardian_commentable = TRUE)
```

## 6. Database contract — `comments`

**Read by:** Stance Detection Agent, Dashboard\
**Written by:** guardian_comments.run (upsert)

| Column | Type | Notes |
|---|---|---|
| comment_id | text PK | Guardian's own ID, globally unique |
| article_id | bigint FK | → articles.id, ON DELETE CASCADE |
| parent_comment_id | text nullable | for threaded replies |
| body_text | text NOT NULL | plain text, HTML stripped |
| author_hash | text | SHA-256 of userProfile.userId |
| created_at | timestamptz | Guardian isoDateTime |
| recommendation_count | int | default 0 |
| fetched_at | timestamptz | default now() |

**Index:** `idx_comments_article_id` on `article_id`.

**Sanitization:**
- `body_text` — HTML stripped via BeautifulSoup.
- `author_hash` — SHA-256 of the raw `userId`. No raw usernames or
  user IDs stored.
- Blocked comments (`status != 'visible'`) are skipped entirely.

## 7. Reddit tables (dormant)
Populated by the one-time `ingest_reddit` script. Not touched by
the runtime pipeline. Available to the Cross-Corpus Matcher and
stance agent as a parallel public-discourse corpus.

- `reddit_posts` — one row per Reddit submission (2,820 rows)
- - `reddit_comments` — one row per comment, FK to post (39,597 rows)

## 8. Preconditions and pipeline ordering

Article branch:
1. `fetch_from_*`                → produces article dicts (no DB writes)
2. `insert_articles(...)`       → articles rows exist with `is_relevant=NULL`
3. `filter_relevance.run()`     → `is_relevant` set to `TRUE`/`FALSE`
4. `llm_verify_relevance.run()` → `llm_relevant` set (on `is_relevant=TRUE`)
5. `preprocess.run()`           → `processing_status` set (on `llm_relevant=TRUE`)

Comment branch (runs after stage 5):
6. `guardian_comments.run()`    → comments row exist

Stages are idempotent and self-filtering, so calling them out of
order is safe but produces no work.

## 9. Integration notes for the Orchestrator
The scripts were built for manual execution. Two changes improve
coordination:

1. **Return summary dicts.** Most `run()` functions still print to
   stdout. Signatures above show the recommended return shape.
2. **Structured logging.** Progress lines go to stdout via `print()`.
   The Orchestrator may want a structured logger.
3. **Two-stage filter.** Stages 3 and 4 must complete before stage 5.
   Both must succeed for preprocessing to have input.
4. **Comments after preprocess.** Do not run `guardian_comments` in
   parallel with stages 3–5. It requires post-preprocess rows.
5. **Guardian fetcher is a separate module** (not part of
   `fetchers.py`). Different auth, different pagination model,
   different response shape.

## 10. Known limitations

### Article branch
- Paywall handling — 403 responses mark the row paywalled
without retry. New outlets may need per-domain handling.
- Relevance keyword drift — filter uses hand-tuned keyword
lists that may lose precision on new sources.
- No automated scheduling (F.2) — collection runs on manual
invocation. Handed off to the Orchestrator per WBS 8.3.
- Prompt injection surface — llm_verify_relevance passes raw
article text to the LLM. Current mitigation: 2,000-char truncation
and a JSON-only system message. Full sanitization owned by the
Security Subsystem (Section 2.9).
- Non-article content — podcast pages and video-only posts
occasionally pass both filters. Detected during preprocessing as
short body text.
- **Guardian query fuzzy-matching** — the Guardian `q` parameter
  matches loosely. Named-model terms (Gemini, Copilot) occasionally
  pull in off-topic articles. Downstream filters drop them.

### Comment branch
- **Undocumented API.** The Guardian Discussion API is internal
  (`discussion.theguardian.com/discussion-api`), not part of the Open
  Platform. Could change without notice. Every call is wrapped in
  try/except.
- **Double-slash route.** The discussion endpoint requires
  `/discussion//p/xxxxx` (double slash — the key carries its own
  leading slash). Easy to get wrong; see `guardian_comments.py`
  comments.
- **Commentable ≠ comments exist.** `guardian_commentable = true`
  means comments were open at publish time, not that any were posted.
  Discussions with zero comments return 404 on the discussion
  endpoint; that's correct behavior.
- **Thread size.** Some discussions have thousands of comments. No cap
  currently. Add one if a single article stalls a run.
- **No comment-level timestamp filtering.** All comments for a
  qualifying article are fetched, regardless of when they were posted
  relative to the article's publication.

## 11. Current state (as of Oct 8, 2026)
- Articles stored (post-dedup):     2,173
- Keyword filter passed:            445
- LLM verified relevant:            371
- Preprocessed successfully:        429
- Guardian articles:                262
- Commentable Guardian articles:    21
- Comments stored:                  29,658
- Unique comment authors:           5,806
