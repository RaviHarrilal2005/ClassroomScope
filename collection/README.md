# INTERFACE.md — Collection & Preprocessing Subsystem

**Owner:** Juan Reyes\
**Consumers:** Orchestrator (Ravi), Analysis Agents, Security Subsystem\
**Last updated:** September 28, 2026\
**Status:** Complete and tested in isolation. Ready for orchestration integration.

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
3. **filter** — mark articles as relevant (F.3)
4. **preprocess** — fetch full article text, extract body (F.5)

Each stage is idempotent. Re-running never produces duplicates and
never corrupts prior results.

## 3. Module inventory

| Module | Stage | Primary function |
|---|---|---|
| `fetchers.py` | fetch | `fetch_all()` |
| `db.py` | store | `insert_articles(articles)` |
| `filter_relevance.py` | filter | `run()` |
| `preprocess.py` | preprocess | `run(limit=None)` |
| `ingest_reddit.py` | (one-time) | `ingest(path, source)` |

## 4. Function contracts

### 4.1 `fetchers.fetch_all()`

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

### 4.2 `db.insert_articles(articles)`
**Signature:**
`def insert_articles(articles: list[dict]) -> tuple[int, int]`

**Arguments:**
`articles` — output of `fetch_all()`

**Returns:** `(inserted_count, skipped_count)`. Rows whose URL
already exists are counted as skipped.

**Side effects:** Writes to `articles` table using
`upsert(on_conflict="url", ignore_duplicates=True)`.

**Notes:**
- Requires RLS INSERT policy on `articles` (present)
- Requires `anon` role to have GRANT INSERT, SELECT on `articles`
- Date normalization happens inside this function via `_parse_date`

### 4.3 `filter_relevance.run()`
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

### 4.4 `preprocess.run(limit=None)`
**Signature:**
`def run(limit: int | None = None) -> dict`

**Arguments:**
- `limit` — max articles to process, or `None` for all pending

**Returns:**
`{"processed": int, "success": int, "failed": int, "paywalled": int}`

**Side effects:** Updates `articles.clean_content`,
`processing_status`, `processing_note`, `processed_at`.

**Preconditions:** Rows exist with `is_relevant = true` AND
`processing_status = 'pending'`.

**Postconditions:** Those rows have `processing_status` in
`{'success', 'failed', 'paywalled'}`.

**Rate limiting:** Sleeps 1 second between fetches. Do NOT run
concurrently on the same source domain.

**Idempotent:** Yes — only processes `pending` rows.

### 4.5 `ingest_reddit.ingest(path, dataset_source)`
**Signature:**
`def ingest(path: str, dataset_source: str) -> None`

**Arguments:**
- `path` — file path to a semicolon-delimited CSV
- `dataset_source` — label written to `dataset_source`, e.g. `'dataset_1'`

**Side effects:** Writes to `reddit_posts` and `reddit_comments`.
Posts first (FK requirement). Orphan comments filtered before insert.

Not part of the runtime pipeline. One-time import only.

### 5. Database contract — `articles`
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
| clean_content | text | NULL until preprocess succeeds |
| processing_status | text | 'pending' / 'success' / 'failed' / 'paywalled' |
| processing_note | text | failure reason |
| processed_at | timestampz | |
| collected_at | timestampz | |

**Row state flow:**
```
INSERT → is_relevant=NULL, processing_status='pending'
filter runs → is_relevant=TRUE/FALSE
preprocess runs → processing_status='success'/'failed'/'paywalled'
```

### 6. Reddit tables
Populated by the one-time `ingest_reddit` script. Not touched by
the runtime pipeline. Available to the Cross-Corpus Matcher and
stance agent as a parallel public-discourse corpus.

- `reddit_posts` — one row per Reddit submission (~4,100 rows)
- `reddit_comments` — one row per comment, FK to post (~54,000 rows)

### 7. Preconditions and pipeline ordering

1. fetch_all()              → produces article dicts (no DB writes)
2. insert_articles(...)     → articles rows exist with is_relevant=NULL
3. filter_relevance.run()   → is_relevant set to TRUE/FALSE
4. preprocess.run()         → processing_status set for relevant rows

Stages are idempotent and self-filtering, so calling them out of
order is safe but produces no work.

### 8. Integration notes for the Orchestrator
The scripts were built for manual execution. Two changes improve
coordination:

1. **Return summary dicts.** The `run()` functions currently print
to stdout. Signatures above show the recommended return shape.
2. **Structured logging.** Progress lines go to stdout via
`print()`. The Orchestrator may want a structured logger.

### 9. Known limitations
- Paywall handling — 403 responses mark the row paywalled
without retry. New outlets may need per-domain handling.
- Relevance keyword drift — filter uses hand-tuned keyword
lists that may lose precision on new sources.
- No automated scheduling (F.2) — collection runs on manual
invocation. Handed off to the Orchestrator per WBS 8.3.
- Domain rate limits — preprocess sleeps 1s between fetches;
running it in parallel across the same outlet may trigger blocks.

### 10. Current state (as of Sept 28, 2026)
- Articles fetched: 745
- Articles stored (post-dedup): 709
- Marked relevant: 279
- Preprocessed successfully: 248
- Reddit posts: 2,820
- Reddit comments: 39,597

