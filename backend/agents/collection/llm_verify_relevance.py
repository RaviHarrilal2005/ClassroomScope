# llm_verify_relevance.py
"""LLM relevance verification — final precision pass after keyword filter.
Usage: python llm_verify_relevance.py [limit]
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from ..supabase_client import get_client

load_dotenv()

API_KEY = os.getenv("TRUSSED_API_KEY")
BASE_URL = os.getenv("TRUSSED_BASE_URL")
MODEL = "gpt-5.6-luna"

PROMPT = """You are a strict relevance filter for a research project analyzing news coverage of GENERATIVE AI IN EDUCATION (K-12 and higher education).

The article is RELEVANT if its primary subject is generative AI in an educational context. Examples:
- AI writing tools (ChatGPT, Claude, etc.) used by students or teachers
- Academic integrity and AI cheating
- University/school AI policies
- Faculty using AI for teaching, grading, or course design
- Impact of AI on student learning or education systems

The article is NOT RELEVANT if:
- It mentions AI and education only in passing while being about another topic
- It's about AI in non-educational contexts (corporate training, healthcare, military, customer service)
- It's about "machine learning" or "AI" in a technical sense unrelated to schools
- It's about education topics without any AI angle

Article title: {title}
Article text: {text}

Respond with JSON only:
{{"relevant": true or false, "reason": "one short sentence"}}"""


def call_luna(title, text):
    prompt = PROMPT.format(title=title or "", text=(text or "")[:2000])
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You classify articles. Output JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 150,
        "reasoning_effort": "none",
    }
    if not BASE_URL:
        return None, None, "TRUSSED_BASE_URL is not set"
    try:
        r = requests.post(BASE_URL, headers=headers, json=body, timeout=60)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return None, None, str(e)

    if content.startswith("```"):
        content = content.strip("`").lstrip("json").strip()

    try:
        parsed = json.loads(content)
        return bool(parsed.get("relevant")), parsed.get("reason", ""), None
    except Exception as e:
        return None, None, f"parse failed: {e}"


def run(limit=None, article_ids=None):
    """
    Verify keyword-relevant rows the LLM has not checked yet.

    article_ids narrows the work to one run's articles. Without it every
    unverified row is checked, which is right for a manual catch-up but
    wrong inside a pipeline run: the run would pay for an LLM call per
    backlog article and record the result as its own.
    """
    if not API_KEY or not BASE_URL:
        raise RuntimeError("TRUSSED_API_KEY / TRUSSED_BASE_URL missing")

    query = (
        get_client().table("articles")
        .select("id, title, content")
        .eq("is_relevant", True)
        .is_("llm_relevant", "null")
    )
    if article_ids is not None:
        query = query.in_("id", list(article_ids))
    if limit:
        query = query.limit(limit)
    rows = query.execute().data or []
    print(f"Verifying {len(rows)} keyword-passing articles with {MODEL}...")

    kept = dropped = failed = 0
    for i, row in enumerate(rows, 1):
        verdict, reason, err = call_luna(row.get("title"), row.get("content"))
        if verdict is None:
            print(f"  [{i}/{len(rows)}] FAILED: {err}")
            failed += 1
            time.sleep(0.5)
            continue

        get_client().table("articles").update({
            "llm_relevant": verdict,
            "llm_relevance_reason": reason,
            "llm_verified_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", row["id"]).execute()

        if verdict:
            kept += 1
        else:
            dropped += 1
        if i % 20 == 0 or i == len(rows):
            print(f"  [{i}/{len(rows)}] kept={kept} dropped={dropped}")

        time.sleep(0.3)

    print(f"\nDone. Kept: {kept}, Dropped: {dropped}, Failed: {failed}.")
    return {"checked": len(rows), "kept": kept, "dropped": dropped, "failed": failed}


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(limit)