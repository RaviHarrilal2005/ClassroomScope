# filter_relevance.py
"""Keyword relevance filter — RECALL pass only.
Loosened deliberately: the LLM verification step downstream
(llm_verify_relevance.py) provides precision. This filter's only
job is to eliminate articles that never mention AI or education
at all.
"""

import re
from db import _supabase

# Any of these signals a GenAI/AI mention.
GAI_PATTERNS = [
    r"\bgenerative ai\b", r"\bgenai\b", r"\bgen ai\b",
    r"\bchatgpt\b", r"\bgpt-?[345]\b", r"\bgpt\b",
    r"\blarge language model", r"\bllm\b", r"\bllms\b",
    r"\bclaude\b", r"\bgemini\b", r"\bcopilot\b",
    r"\bartificial intelligence\b", r"\bmachine learning\b",
    r"\bai\b",  # word boundary — won't match "email", "said", etc.
]

# Any of these signals an education context.
EDU_PATTERNS = [
    r"\bstudent", r"\bteacher", r"\bprofessor", r"\bfaculty",
    r"\bcurriculum\b", r"\bclassroom", r"\buniversity\b",
    r"\buniversities\b", r"\bcollege", r"\bhigher ed",
    r"\bk-12\b", r"\bschool", r"\beducation",
    r"\bacademic\b", r"\bessay\b", r"\bhomework\b",
    r"\bassignment", r"\bexam\b", r"\bpedagog",
]

_GAI = re.compile("|".join(GAI_PATTERNS), re.IGNORECASE)
_EDU = re.compile("|".join(EDU_PATTERNS), re.IGNORECASE)


def is_relevant(title, content):
    text = f"{title or ''}\n{content or ''}"
    return bool(_GAI.search(text)) and bool(_EDU.search(text))


def run():
    rows = (
        _supabase.table("articles")
        .select("id, title, content")
        .is_("is_relevant", "null")
        .execute()
    ).data or []
    print(f"Checking {len(rows)} unclassified articles...")

    relevant = 0
    for row in rows:
        flag = is_relevant(row.get("title"), row.get("content"))
        _supabase.table("articles").update(
            {"is_relevant": flag}
        ).eq("id", row["id"]).execute()
        relevant += int(flag)

    print(f"Marked {relevant} relevant, {len(rows) - relevant} irrelevant.")
    return {"checked": len(rows), "relevant": relevant,
            "irrelevant": len(rows) - relevant}


if __name__ == "__main__":
    run()