"""
The team's agents, wrapped in the coordinator's Agent contract.

Each class is a thin shell over a teammate's module: it translates the
RunContext into that module's arguments, and the module's result into
the summary dict the coordinator expects. The real work stays in
collection/, security/, classification/ and topic/, so an owner can
keep editing their own code without touching orchestrator code.

Two rules from the contract are worth repeating here, because the
standalone scripts break both by design:

  * Raise on failure. The scripts catch their own errors and print
    them, so a failed run looks like a run that found nothing. The
    coordinator handles retries, fallbacks and recording, and it can
    only do that if it sees the exception.
  * Never retry internally. Retry counts live in orchestrator/retry.py.

Which stages are real (see docs/pipeline-coordinator.md):

  collection      real - CollectionAgent
  security        real - SecurityAgent
  classification  real - ClassificationAgent ('baseline' or 'luna')
  topic           real - TopicAgent (needs the saved model file)
  sentiment       stub - agents/sentiment/ is a standalone script, not
                  wired in yet
  stance          stub - no implementation on any branch yet
  aggregation     stub - no implementation yet
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence

from orchestrator.agents import Agent
from orchestrator.models import RunContext

from .config import optional_key
from .supabase_client import get_client

logger = logging.getLogger(__name__)

# PostgREST puts the filter in the URL, so a huge `in` list produces a
# request line long enough for the server to reject. Well above any
# realistic single run's collection.
CHUNK = 200


def _chunks(values: Sequence[Any], size: int = CHUNK) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _select_by_id(table: str, columns: str, ids: Sequence[int]) -> List[Dict[str, Any]]:
    """Rows from `table` whose id is in `ids`, fetched in safe-sized batches."""
    rows: List[Dict[str, Any]] = []
    client = get_client()
    for batch in _chunks(list(ids)):
        result = client.table(table).select(columns).in_("id", list(batch)).execute()
        rows.extend(result.data or [])
    return rows


# ---------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------
class CollectionAgent(Agent):
    """
    Fetch -> store -> keyword filter -> LLM relevance check -> preprocess,
    then report the IDs.

    Returns the articles stored this run that analysis can actually use:
    confirmed relevant by the LLM and preprocessed successfully. An
    article that was stored but turned out to be irrelevant, or whose
    page could not be downloaded, has no `clean_content`, and every
    analysis agent reads `clean_content` — passing its ID on would just
    produce four failures further down the pipeline.

    The keyword filter is only a recall pass. The LLM check sets
    llm_relevant, and preprocess downloads nothing else, so without
    TRUSSED_API_KEY and TRUSSED_BASE_URL no article can come out of a
    run. The stage fails up front instead of spending API quota first.

    sources           which fetchers to use; None means all of them
    preprocess_limit  cap on pages downloaded per run (each costs ~1s)
    backlog           skip fetching and return articles already stored
                      and analysis-ready. For exercising the rest of
                      the pipeline against the existing corpus without
                      spending API quota - see run_pipeline.py --backlog.
    backlog_limit     cap on the IDs returned in backlog mode
    """

    name = "collection"

    def __init__(
        self,
        sources: Optional[Sequence[str]] = None,
        preprocess_limit: Optional[int] = None,
        backlog: bool = False,
        backlog_limit: int = 200,
    ) -> None:
        self.sources = list(sources) if sources else None
        self.preprocess_limit = preprocess_limit
        self.backlog = backlog
        self.backlog_limit = backlog_limit

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        if self.backlog:
            return self._from_backlog()

        from .collection import db, fetchers, filter_relevance, llm_verify_relevance, preprocess

        if not (optional_key("TRUSSED_API_KEY") and optional_key("TRUSSED_BASE_URL")):
            raise RuntimeError(
                "Collection's relevance check needs TRUSSED_API_KEY and TRUSSED_BASE_URL in backend/.env"
            )

        fetched = fetchers.fetch_all(self.sources)
        logger.info("Run %s: collection fetched %d article(s)", ctx.run_id, len(fetched))

        stored_ids, skipped = db.insert_articles_returning_ids(fetched)
        logger.info(
            "Run %s: collection stored %d new, %d already known",
            ctx.run_id, len(stored_ids), skipped,
        )
        if not stored_ids:
            return {"article_ids": [], "fetched": len(fetched), "stored": 0, "duplicates": skipped}

        relevance = filter_relevance.run(article_ids=stored_ids)
        verified = llm_verify_relevance.run(article_ids=stored_ids)
        # Every call failing is an outage or a bad key, not a verdict, and
        # leaves nothing for preprocess. Raise rather than report a run
        # that found nothing, as the LLM classifier does.
        if verified["checked"] and verified["failed"] == verified["checked"]:
            raise RuntimeError(
                f"The LLM relevance check failed on all {verified['checked']} article(s)"
            )
        processing = preprocess.run(limit=self.preprocess_limit, article_ids=stored_ids)

        usable = self._analysis_ready(stored_ids)
        return {
            "article_ids": usable,
            "fetched": len(fetched),
            "stored": len(stored_ids),
            "duplicates": skipped,
            "relevant": relevance["relevant"],
            "llm_relevant": verified["kept"],
            "preprocessed": processing["success"],
        }

    def _analysis_ready(self, ids: Sequence[int]) -> List[int]:
        """Of `ids`, the ones the LLM confirmed and preprocess succeeded on."""
        rows = []
        client = get_client()
        for batch in _chunks(list(ids)):
            result = (
                client.table("articles")
                .select("id")
                .in_("id", list(batch))
                .eq("llm_relevant", True)
                .eq("processing_status", "success")
                .execute()
            )
            rows.extend(result.data or [])
        return sorted(r["id"] for r in rows)

    def _from_backlog(self) -> Dict[str, Any]:
        result = (
            get_client()
            .table("articles")
            .select("id")
            .eq("llm_relevant", True)
            .eq("processing_status", "success")
            .order("id")
            .limit(self.backlog_limit)
            .execute()
        )
        ids = sorted(r["id"] for r in (result.data or []))
        logger.info("Collection in backlog mode: %d already-stored article(s)", len(ids))
        return {"article_ids": ids, "backlog": True, "fetched": 0, "stored": 0}


# ---------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------
class SecurityAgent(Agent):
    """
    Screen each collected article's text before any analysis reads it.

    Runs agents/security/text_filter.py over the article's title and
    clean_content. An article the filter rejects is quarantined: its ID
    is left out of approved_ids, so no analysis agent is given it.

    max_length raises the filter's cap for article bodies. The filter's
    own default is 50,000 characters, and the longest article in the
    corpus is twice that, so the default would quarantine the longest
    articles for length alone.

    TWO THINGS THIS DOES NOT DO, both deliberate:

      * It does not persist the quarantine decision. The security
        owners' agents/security/quarantine.py writes rejections to
        quarantined_content, but over a direct Postgres connection
        that the pipeline does not have, and that table was created
        outside this repo's migrations. Decisions are logged at WARNING
        and counted by reason in the returned summary, which is enough
        to see what a run rejected and why, but they are not queryable
        after the fact. See docs/pipeline-coordinator.md.
      * It does not write the filter's redacted text back. The filter
        redacts emails, phone numbers, SSNs and street addresses in the
        text it returns, but analysis agents read clean_content straight
        from the database, so they still see the unredacted article.
        Screening currently decides pass/quarantine only.

    The filter scores 44/45 against its own adversarial suite
    (agents/security/adversarial_test_set.py). The miss is a full name,
    which a pattern cannot catch; the filter's own docs say it needs NER.
    """

    name = "security"

    # 101,377 characters is the longest article in the corpus today, so
    # this leaves real headroom while still bounding the work.
    MAX_ARTICLE_LENGTH = 200_000

    def __init__(self, max_length: Optional[int] = None) -> None:
        self.max_length = max_length or self.MAX_ARTICLE_LENGTH

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        from .security import text_filter

        rows = _select_by_id("articles", "id, title, clean_content", ctx.article_ids)
        found = {r["id"] for r in rows}

        approved: List[int] = []
        quarantined: List[int] = []
        reasons: Dict[str, int] = {}

        for row in rows:
            text = f"{row.get('title') or ''}\n\n{row.get('clean_content') or ''}".strip()
            result = self._screen(text_filter, text)
            if result.passed:
                approved.append(row["id"])
                continue
            quarantined.append(row["id"])
            reason = result.reason or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
            logger.warning(
                "Run %s: article %s quarantined (%s) matched=%r",
                ctx.run_id, row["id"], reason, result.flagged_pattern,
            )

        # An ID we were given but could not read is not screened, so it
        # cannot be approved. Treat it as quarantined rather than
        # silently dropping it, which would leave the counts not adding up.
        missing = [i for i in ctx.article_ids if i not in found]
        if missing:
            quarantined.extend(missing)
            reasons["not_found"] = reasons.get("not_found", 0) + len(missing)
            logger.warning(
                "Run %s: %d collected article(s) could not be read back for screening: %s",
                ctx.run_id, len(missing), missing[:10],
            )

        if quarantined:
            logger.warning(
                "Run %s: security quarantined %d of %d article(s): %s",
                ctx.run_id, len(quarantined), len(ctx.article_ids),
                ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())),
            )

        return {
            "approved_ids": sorted(approved),
            "quarantined_ids": sorted(quarantined),
            "quarantine_reasons": reasons,
        }

    def _screen(self, text_filter: Any, text: str) -> Any:
        """Run the filter with the article-sized length cap."""
        original = text_filter.MAX_TEXT_LENGTH
        text_filter.MAX_TEXT_LENGTH = self.max_length
        try:
            return text_filter.sanitize_text(text)
        finally:
            text_filter.MAX_TEXT_LENGTH = original


# ---------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------
class ClassificationAgent(Agent):
    """
    Stakeholder group and source type for each approved article.

    classifier  'baseline' - the keyword scorer. No API, deterministic,
                             always available.
                'luna'     - the LLM classifier. Needs TRUSSED_API_KEY
                             and TRUSSED_BASE_URL.

    Both write to classification_results tagged with which one produced
    the row, so the two can be compared (classification README, F.10).

    Rows are written for the approved articles only. The standalone
    scripts classify everything in the table; inside a run, the stage
    must stay within the articles security approved.
    """

    name = "classification"

    # Seconds between LLM calls, matching the standalone script.
    CALL_INTERVAL = 0.3

    def __init__(self, classifier: str = "baseline", call_interval: Optional[float] = None) -> None:
        if classifier not in ("baseline", "luna"):
            raise ValueError(f"classifier must be 'baseline' or 'luna', got '{classifier}'")
        self.classifier = classifier
        self.call_interval = self.CALL_INTERVAL if call_interval is None else call_interval
        self.name = f"classification_{classifier}"

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        rows = _select_by_id("articles", "id, title, clean_content, url", ctx.approved_ids)
        if not rows:
            return {"processed": 0, "classifier": self.classifier}

        if self.classifier == "baseline":
            records = self._baseline(rows)
        else:
            records = self._luna(rows)

        written = self._write(records)
        return {
            "processed": written,
            "classifier": self.classifier,
            "skipped": len(rows) - written,
        }

    def _baseline(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from datetime import datetime, timezone

        from .classification import classify_baseline as baseline

        records = []
        for row in rows:
            group, confidence = baseline.classify_stakeholder(row.get("title"), row.get("clean_content"))
            source_type, source_confidence = baseline.classify_source_type(row.get("url") or "")
            records.append({
                "article_id": row["id"],
                "stakeholder_category": group,
                "confidence": confidence,
                "source_type": source_type,
                "source_type_confidence": source_confidence,
                "classifier": "baseline_keyword",
                "classified_at": datetime.now(timezone.utc).isoformat(),
            })
        return records

    def _luna(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from datetime import datetime, timezone

        from .classification import classify_luna as luna

        if not luna.API_KEY or not luna.BASE_URL:
            raise RuntimeError(
                "The Luna classifier needs TRUSSED_API_KEY and TRUSSED_BASE_URL in backend/.env"
            )

        records, failures = [], []
        for index, row in enumerate(rows):
            # One call per article. The standalone script paces itself and
            # so does this: a run over the whole backlog would otherwise
            # be a few hundred requests as fast as the loop can issue them.
            if index:
                time.sleep(self.call_interval)
            prompt = luna.build_prompt(row.get("title"), row.get("clean_content") or "")
            category, confidence, error = luna.call_luna(prompt)
            if category is None:
                failures.append(f"article {row['id']}: {error}")
                continue
            source_type, source_confidence = luna.classify_source_type(row.get("url") or "")
            records.append({
                "article_id": row["id"],
                "stakeholder_category": category,
                "confidence": confidence,
                "source_type": source_type,
                "source_type_confidence": source_confidence,
                "classifier": luna.CLASSIFIER_TAG,
                "classified_at": datetime.now(timezone.utc).isoformat(),
            })

        # Every single call failing is an outage or a bad key, not a
        # classification result. Raise so the coordinator retries and
        # then falls back, rather than recording an empty success.
        if rows and not records:
            raise RuntimeError(
                f"Luna classified none of {len(rows)} article(s). First error: "
                f"{failures[0] if failures else 'unknown'}"
            )
        if failures:
            logger.warning("Luna failed on %d of %d article(s)", len(failures), len(rows))
        return records

    @staticmethod
    def _write(records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        client = get_client()
        for batch in _chunks(records):
            client.table("classification_results").upsert(
                list(batch), on_conflict="article_id,classifier"
            ).execute()
        return len(records)


# ---------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------
class TopicAgent(Agent):
    """
    A topic for each approved article, from the saved BERTopic model.

    agents/topic/topic_model.py has its own TopicAgent that already
    follows the agent contract; this shell only defers importing it.
    That module loads BERTopic and its ML stack, and building the
    registry must not need any of it.

    The stage needs the saved model file, which is gitignored (see
    agents/topic/TOPIC_IDENTITY.md). Without it, or with a file whose
    checksum is not registered in topic_catalog.json, the stage fails;
    it never trains a replacement.
    """

    name = "topic"

    def run(self, ctx: RunContext) -> Dict[str, Any]:
        from .topic import topic_model

        return topic_model.TopicAgent().run(ctx)
