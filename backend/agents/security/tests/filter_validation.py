"""
filter_validation.py

Runs the sanitization filter over REAL data instead of synthetic cases, in
report-only mode. Nothing is modified, rejected, or deleted — this produces
counts and samples so we can say what the filter actually finds in our
corpus.

Two targets:
  1. articles.clean_content   — the live S.4/S.5 surface (709 rows)
  2. reddit_comments.text     — imported user-generated text (39,597 rows)

Setup:
    pip install bleach psycopg2-binary python-dotenv
    # .env  (never commit this)
    PGHOST=db.<project-ref>.supabase.co
    PGPORT=5432
    PGDATABASE=postgres
    PGUSER=collection_agent
    PGPASSWORD=...

Run:
    python3 filter_validation.py > validation_report.txt
"""

import os
import re
import sys, pathlib
from collections import Counter
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import psycopg2
from dotenv import load_dotenv



from text_filter import sanitize_comment as sanitize_text

load_dotenv()

SAMPLE_LIMIT = 3      # examples printed per flag category
TRUNCATE = 160        # chars shown per sample


# Reddit junk detection (quality, not security)

JUNK_CHECKS = [
    ("deleted_removed", lambda t: t.strip() in ("[deleted]", "[removed]")),
    ("mod_removed", lambda t: bool(re.search(
        r"removed by (?:reddit|moderator)|this comment was removed", t, re.I))),
    ("bot_boilerplate", lambda t: bool(re.search(
        r"i am a bot|performed automatically|contact the moderators", t, re.I))),
    ("too_short", lambda t: len(t.strip()) < 15),
]


def classify_junk(text):
    if not text:
        return "empty"
    for name, check in JUNK_CHECKS:
        if check(text):
            return name
    return None


# ---------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------
def scan(cur, table, text_col, id_col, check_junk=False):
    cur.execute(f"select {id_col}, {text_col} from public.{table}")
    rows = cur.fetchall()

    counts = Counter()
    samples = {}

    for row_id, text in rows:
        counts["total"] += 1

        if check_junk:
            junk = classify_junk(text or "")
            if junk:
                counts[f"junk:{junk}"] += 1
                samples.setdefault(f"junk:{junk}", []).append((row_id, text))
                # junk rows still get screened — a [removed] row can't hide a
                # payload, but a short row can
                if junk != "deleted_removed":
                    pass
                else:
                    continue

        try:
            result = sanitize_text(text)
        except Exception as e:
            counts["crash"] += 1
            samples.setdefault("crash", []).append((row_id, f"{type(e).__name__}: {e}"))
            continue

        if result.passed:
            counts["clean_or_redacted"] += 1
            # redact-and-pass: PII was found but the row still passes
            if result.clean_text != (text or ""):
                counts["pii_redacted"] += 1
                samples.setdefault("pii_redacted", []).append((row_id, text))
        else:
            key = f"rejected:{result.reason}"
            counts[key] += 1
            samples.setdefault(key, []).append((row_id, text))

    return counts, samples


def report(title, counts, samples):
    total = counts.get("total", 0)
    print(f"\n{'=' * 68}\n{title}  —  {total} rows\n{'=' * 68}")

    for key in sorted(counts):
        if key == "total":
            continue
        n = counts[key]
        pct = (n / total * 100) if total else 0
        print(f"  {key:<42} {n:>7}  ({pct:5.2f}%)")

    for key in sorted(samples):
        if not key.startswith(("rejected:", "crash")):
            continue
        print(f"\n  -- samples: {key} --")
        for row_id, text in samples[key][:SAMPLE_LIMIT]:
            snippet = (text or "")[:TRUNCATE].replace("\n", " ")
            print(f"     [{row_id}] {snippet}")


def main():
    try:
        conn = psycopg2.connect(
            host=os.environ["PGHOST"],
            port=os.environ.get("PGPORT", 5432),
            dbname=os.environ.get("PGDATABASE", "postgres"),
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            sslmode="require",
        )
    except KeyError as e:
        sys.exit(f"Missing env var: {e}. See setup notes at the top of this file.")

    print("ClassroomScope — Filter Validation (report-only, no writes)")
    print(f"Connected as: {os.environ['PGUSER']}")

    with conn, conn.cursor() as cur:
        counts, samples = scan(cur, "articles", "clean_content", "id")
        report("articles.clean_content  (live pipeline surface, S.4/S.5)", counts, samples)

        counts, samples = scan(cur, "reddit_comments", "text", "id", check_junk=True)
        report("reddit_comments.text  (imported benchmark data — FLAG ONLY)", counts, samples)

    conn.close()
    print("\nNo rows were modified. Reddit rows remain intact as benchmark ground truth.")


if __name__ == "__main__":
    main()
