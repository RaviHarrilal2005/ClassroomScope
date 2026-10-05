"""
quarantine.py — persists filter rejections to the audit log (S.8).

The filter itself stays pure (text in, result out) so it remains testable
without a database. This module is the only place that writes.

Usage inside the collection/screening loop:

    from quarantine import screen_and_store

    ok, clean = screen_and_store(conn, raw_text,
                                 source_table="articles",
                                 source_id=str(article_id),
                                 run_id=current_run_id)
    if ok:
        store(clean)        # redacted text, safe to persist
    else:
        skip()              # rejection already logged for review
"""

try:
    from .text_filter import sanitize_text
except ImportError:  # running the file directly, not importing the package
    from text_filter import sanitize_text

EXCERPT_CHARS = 400


def screen_and_store(conn, raw_text, source_table, source_id, run_id=None):
    """Screen text; log a rejection if it fails.

    Returns (passed, clean_text). clean_text is None when rejected.
    A logging failure never blocks the pipeline - the screening verdict
    still stands, we just lose the audit row and say so.
    """
    result = sanitize_text(raw_text)

    if result.passed:
        return True, result.clean_text

    excerpt = (raw_text or "")[:EXCERPT_CHARS] if isinstance(raw_text, str) else None

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into public.quarantined_content
                    (source_table, source_id, run_id, reason, flagged_detail, excerpt)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (source_table, source_id, run_id) do nothing
                """,
                (source_table, source_id, run_id,
                 result.reason, result.flagged_pattern, excerpt),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Don't swallow this silently - a missing audit row is a finding.
        print(f"[quarantine] failed to log {source_table}:{source_id} -> {e}")

    return False, None


def unreviewed(conn, limit=50):
    """Rows awaiting human review - the false-positive workflow."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select id, source_table, source_id, reason, flagged_detail, excerpt
            from public.quarantined_content
            where reviewed = false
            order by quarantined_at desc
            limit %s
            """,
            (limit,),
        )
        return cur.fetchall()
