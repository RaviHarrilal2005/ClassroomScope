# ingest_reddit.py
"""Import Reddit dataset CSVs into Supabase.
Usage:
    python ingest_reddit.py reddit_dataset_2.csv dataset_2
    python ingest_reddit.py reddit_dataset_1.csv dataset_1
"""

import sys
import csv
from datetime import datetime, timezone

from db import _supabase


def parse_utc(value):
    """Accepts unix seconds (int or str) or ISO 8601. Returns ISO string or None."""
    if value is None or value == "":
        return None

    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        pass

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def to_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def ingest(path, dataset_source):
    posts, comments = [], []
    bad_rows = 0

    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            row_type = (row.get("type") or "").strip().lower()

            if row_type == "post":
                if not row.get("id"):
                    bad_rows += 1
                    continue
                posts.append({
                    "id": row["id"],
                    "subreddit": row.get("subreddit") or None,
                    "specific_subreddit": row.get("specific_subreddit") or None,
                    "title": row.get("title") or None,
                    "text": row.get("text") or "",
                    "created_utc": parse_utc(row.get("created_utc")),
                    "score": to_int(row.get("score")),
                    "num_comments": to_int(row.get("num_comments")),
                    "stakeholder_group": row.get("stakeholder_group") or None,
                    "dataset_source": dataset_source,
                })

            elif row_type == "comment":
                if not row.get("id") or not row.get("post_id"):
                    bad_rows += 1
                    continue
                comments.append({
                    "id": row["id"],
                    "post_id": row["post_id"],
                    "text": row.get("text") or "",
                    "created_utc": parse_utc(row.get("created_utc")),
                    "score": to_int(row.get("score")),
                    "stakeholder_group": row.get("stakeholder_group") or None,
                    "dataset_source": dataset_source,
                })

    # Dedupe by id — Dataset 1 contains duplicate rows.
    posts = list({p["id"]: p for p in posts}.values())
    comments = list({c["id"]: c for c in comments}.values())

    # Only keep comments whose parent post is in this file.
    post_ids = {p["id"] for p in posts}
    orphans = [c for c in comments if c["post_id"] not in post_ids]
    comments = [c for c in comments if c["post_id"] in post_ids]

    print(f"Parsed: {len(posts)} posts, {len(comments)} valid comments, "
          f"{len(orphans)} orphan comments dropped, "
          f"{bad_rows} skipped (missing id)")

    # Posts first — comments FK to them.
    if posts:
        try:
            _supabase.table("reddit_posts").upsert(
                posts, on_conflict="id"
            ).execute()
            print(f"Upserted {len(posts)} posts.")
        except Exception as e:
            print(f"Post insert error: {e}")
            return

    # Comments in batches so a single oversized request doesn't fail.
    batch_size = 500
    inserted = 0
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        try:
            _supabase.table("reddit_comments").upsert(
                batch, on_conflict="id"
            ).execute()
            inserted += len(batch)
            print(f"  comments batch {i // batch_size + 1}: "
                  f"{inserted}/{len(comments)}")
        except Exception as e:
            print(f"Comment batch error at offset {i}: {e}")
            return

    print(f"\nDone. Posts: {len(posts)}. Comments: {inserted}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python ingest_reddit.py <csv_path> <dataset_source>")
        sys.exit(1)
    ingest(sys.argv[1], sys.argv[2])